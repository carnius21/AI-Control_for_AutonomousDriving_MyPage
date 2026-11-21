"""Matched first-fork diagnosis and two-route PPO fine-tuning."""
from utils.failure_log import FailureLog
from concurrent.futures import ProcessPoolExecutor
import json
import numpy as np
from utils.experiment_a import ROOT, make, m, torch
from utils.run_experiment_a import save

OUT = ROOT / "paired_fork_pilot"
ARM = "sensor200_pass"
ROUTES = ("route_13", "route_16")
TEST = (911301, 911302, 911303)

def evaluate(env, agent, seeds):
    rows = []
    for seed in seeds:
        for route in ROUTES:
            obs, _ = env.reset(seed=seed, options={"route": route})
            passed = False
            changes = []
            failure = FailureLog()
            while True:
                edge, lane, path, idx, _, _, _, _, rem = env.snapshot
                if env.record:
                    failure.before(env,obs)
                act = agent.predict(obs)
                obs, _, done, cut, info = env.step(act)
                post = env.snapshot
                if post and edge == path[0] and post[0] == edge and post[1] != lane:
                    changes.append([lane, post[1], round(rem)])
                if post and post[0] == path[1]:
                    passed = True
                if env.record and not (done or cut):
                    failure.after(env,info)
                if done or cut:
                    result = "collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                    rows.append(dict(route=route, seed=seed, passed=passed, outcome=result,
                        last_edge=edge, last_lane=lane, remaining=round(rem), changes=changes,
                        failure=failure.after(env,info,result) if env.record else None,
                        crash={k:v for k,v in env.events.items() if k.startswith("collision_")}))
                    break
    return rows

def inputs(env,agent):
    rows=[]
    for route in ROUTES:
        obs,_=env.reset(seed=TEST[0],options={"route":route})
        snaps=[]
        for threshold in (10000,399,199,99):
            while env.snapshot[8]>threshold:
                obs,_,done,cut,_=env.step(np.array([0.3,0.],dtype=np.float32))
                assert not (done or cut)
            snaps.append(dict(distance=round(env.snapshot[8],2),lane=env.snapshot[1],obs=obs.tolist(),action=agent.predict(obs).tolist()))
        rows.append(snaps)
    return rows

class BalancedPair:
    def __init__(self,env,seed):
        self.env=env
        self.n=0
        self.seed=seed
    def reset(self):
        route=ROUTES[self.n%2]
        seed=100000*self.seed+self.n//2
        self.n+=1
        return self.env.reset(seed=seed,options={"route":route})
    def step(self,action):
        return self.env.step(action)

def run(seed):
    torch.set_num_threads(1)
    folder=OUT/str(seed)
    folder.mkdir(parents=True,exist_ok=True)
    agent=m.PPO(obs_dim=40,act_dim=2,buffer=m.RolloutBuffer(),seed=seed,device="cpu",
        hidden_sizes=(256,256),n_steps=2048,n_epochs=10,minibatch_size=64,lr=.0001,lane_entropy_coef=.002,lane_keep_bias=1.)
    agent.load(str(ROOT/f"{ARM}_{seed}"/"policy_650000.pt"))
    report={}
    for target in (0,8192,24576):
        if target:
            env=make("none",ARM,seed,folder/"train")
            env.ego_depart_lane="1"
            pair=BalancedPair(env,seed)
            pair.n=previous_episodes
            try:
                obs,_=pair.reset()
                stats=[0.,0]
                for _ in range((target-prev)//2048):
                    obs,last,_=agent.collect_rollout(pair,obs,ep_stats=stats,steps=2048)
                    adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                    agent.update(adv,ret)
                previous_episodes=pair.n
            finally: env.close()
            agent.save(str(folder/f"policy_plus_{target}.pt"))
        else: previous_episodes=0
        prev=target
        env=make("none",ARM,seed,folder/"empty")
        env.ego_depart_lane="1"
        try:
            if not target: report["fixed_path"]=inputs(env,agent)
            rows=evaluate(env,agent,TEST[:1])
        finally: env.close()
        report[str(target)]={"none":rows}
        save(folder/"report.json",report)
        if target==0 or all(x["passed"] for x in rows):
            env=make("high_real_ratio",ARM,seed,folder/"traffic")
            env.ego_depart_lane="1"
            env.record=True
            try: report[str(target)]["high"]=evaluate(env,agent,TEST)
            finally: env.close()
            save(folder/"report.json",report)
    return seed
if __name__=="__main__":
    with ProcessPoolExecutor(3) as pool: print(list(pool.map(run,(11,22,33))))

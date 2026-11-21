"""Controlled high-demand continuation from the frozen A0 600k policy."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import sys
from utils.experiment_a import ROOT, SIZE, RoadEnv, make, m, np, torch, traci
from utils.run_experiment_a import save

OUT=ROOT/"front_trials_v1"
PARENT=ROOT/"A0_11"/"policy_600000.pt"
ARMS=("control","gap","brake")
MARKS=(10000,20000,30000,40000,50000)


def patched(obs,leader,relative_speed):
    if leader and leader[0] and leader[1]<0:
        obs[9]=0.
        obs[10]=np.clip(relative_speed,-1.,1.)
    return obs


def hazard(obs):
    gap=50*float(obs[9])
    closing=-27.8*float(obs[10])
    return closing>.5 and gap<2.5*closing


class TrialEnv(RoadEnv):
    def _get_obs(self):
        obs=super()._get_obs()
        self.lead=None
        if self.snapshot is not None:
            self.lead=traci.vehicle.getLeader(self.ego_id,self.visibility)
            if self.condition!="control" and self.lead and self.lead[0] and self.lead[1]<0:
                relative=(traci.vehicle.getSpeed(self.lead[0])-self.snapshot[7])/self.vmax
                patched(obs,self.lead,relative)
        self.policy_input=obs
        return obs

    def step(self,action):
        danger=hazard(self.policy_input)
        accel=float(action[self.accel_index])
        obs,reward,done,cut,info=super().step(action)
        cost=.15 if self.condition=="brake" and danger and accel>=0 and not done else 0.
        info["no_brake_cost"]=cost
        return obs,reward-cost,done,cut,info


def setup(arm,sub):
    folder=OUT/arm
    folder.mkdir(parents=True,exist_ok=True)
    env=make("high_real_ratio","A0",11,folder/sub)
    env.__class__=TrialEnv
    env.condition=arm
    torch.set_num_threads(1)
    agent=m.PPO(obs_dim=SIZE,act_dim=2,buffer=m.RolloutBuffer(),seed=11,device="cpu",
                hidden_sizes=(256,256),n_steps=2048,n_epochs=10,minibatch_size=64,
                lr=.0001,lane_entropy_coef=.002,lane_keep_bias=1.)
    return folder,env,agent


def train(arm):
    folder,env,agent=setup(arm,"train_map")
    agent.load(str(PARENT))
    try:
        obs,_=env.reset()
        ep=[0.,0]
        for mark in MARKS:
            while agent.num_timesteps<mark:
                obs,last,_=agent.collect_rollout(env,obs,steps=min(2048,mark-agent.num_timesteps),ep_stats=ep)
                adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                agent.update(adv,ret)
                save(folder/"progress.json",dict(steps=agent.num_timesteps))
            agent.save(str(folder/f"policy_{mark}.pt"))
    finally:
        env.close()


def evaluate(job):
    arm,mark=job
    folder,env,agent=setup(arm,f"eval_map_{mark}")
    agent.load(str(folder/f"policy_{mark}.pt" if mark else PARENT))
    rows=[]
    try:
        for idx,route in enumerate(m.ROUTES):
            for rep in range(3):
                seed=41001+idx+100*rep
                obs,_=env.reset(seed=seed,options={"route":route})
                stats=Counter()
                while True:
                    speed=env.snapshot[7]
                    lane=traci.vehicle.getLaneID(env.ego_id)
                    leader=env.lead
                    other_lane=traci.vehicle.getLaneID(leader[0]) if leader and leader[0] else None
                    # Same physical danger denominator in all arms, even if A0 masks the sample.
                    physical=obs.copy()
                    if leader and leader[0] and leader[1]<0:
                        patched(physical,leader,(traci.vehicle.getSpeed(leader[0])-speed)/env.vmax)
                        stats["neg_gap"]+=1
                    danger=hazard(physical)
                    cmd=agent.predict(obs,deterministic=True)
                    if danger:
                        stats["risk"]+=1
                        stats["brake_cmd"]+=int(cmd[env.accel_index]<0)
                        stats["visible_risk"]+=int(hazard(obs))
                    obs,_,done,cut,info=env.step(cmd)
                    if danger and env.snapshot is not None:
                        stats["response_observed"]+=1
                        stats["decelerated"]+=int(env.snapshot[7]<speed-.01)
                    stats["penalties"]+=int(info["no_brake_cost"]>0)
                    if done or cut:
                        outcome="collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                        kind=""
                        if info["collided"]:
                            kind="unknown"
                            for c in traci.simulation.getCollisions():
                                if env.ego_id not in (c.collider,c.victim):continue
                                if c.type=="side":kind="side"
                                elif c.type=="junction" and other_lane!=lane:kind="junction"
                                elif c.collider==env.ego_id and leader and c.victim==leader[0]:kind="front"
                                elif c.victim==env.ego_id:kind="struck"
                                break
                        rows.append(dict(route=route,seed=seed,outcome=outcome,kind=kind,metrics=stats))
                        break
        assert len(rows)==48
        save(folder/f"eval_{mark}.json",rows)
    finally:
        env.close()


def preflight():
    obs=np.zeros(SIZE,np.float32)
    obs[9:11]=1
    for lead in (None,("",-1)):
        assert tuple(patched(obs.copy(),lead,-.5)[9:11])==(1.,1.)
    assert tuple(patched(obs.copy(),("valid",-1),-.5)[9:11])==(0.,-.5)
    assert hazard(patched(obs.copy(),("valid",-1),-.5))
    save(OUT/"design.json",dict(parent=str(PARENT),sha256=sha256(PARENT.read_bytes()).hexdigest(),seed=11,
         arms=list(ARMS),marks=MARKS,stage="high_real_ratio",risk="closing>0.5m/s and TTC<2.5s",
         penalty="0.15 per nonterminal at-risk step with accel_raw >= 0", dt=.2,depart_lane=0))


def run():
    from time import sleep
    OUT.mkdir(exist_ok=True)
    preflight()
    with ProcessPoolExecutor(max_workers=3) as trainers, ProcessPoolExecutor(max_workers=3) as evaluators:
        work=[trainers.submit(train,a) for a in ARMS]
        pending=[(a,s) for s in MARKS for a in ARMS]
        evals=[evaluators.submit(evaluate,("control",0))]
        while pending:
            for f in work:
                if f.done():f.result()
            for job in pending.copy():
                arm,s=job
                path=OUT/arm/f"policy_{s}.pt"
                if path.exists() and path.stat().st_size==PARENT.stat().st_size:
                    evals.append(evaluators.submit(evaluate,job))
                    pending.remove(job)
                elif (OUT/arm/"progress.json").exists() and path.exists() and (all(f.done() for f in work) or json.loads((OUT/arm/"progress.json").read_text())["steps"]>s):
                    evals.append(evaluators.submit(evaluate,job))
                    pending.remove(job)
            sleep(2)
        for f in work+evals:f.result()


if __name__=="__main__":
    run()

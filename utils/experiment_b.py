"""Paired high-demand PPO experiment. Run as python -m utils.experiment_b."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import inspect
import itertools
import json
import random
import subprocess
import sys
import xml.etree.ElementTree as ET

from utils.experiment_a import make, m, torch, traci, STAGES
from utils.run_experiment_a import save
from env.ic_experiment import RAMPS
from env import ic_experiment as ic

OUT = m.ROOT / "results" / "experiment_b_20261121"
STEPS = range(0, 600001, 50000)
HP = dict(hidden_sizes=(256,256), n_steps=2048, n_epochs=10, minibatch_size=64,
          lr=.0001, lane_entropy_coef=.002, lane_keep_bias=1., device="cpu")


def agent_for(seed):
    return m.PPO(obs_dim=38, act_dim=2, buffer=m.RolloutBuffer(), seed=seed, **HP)


def digest(agent):
    h = hashlib.sha256()
    for name, value in agent.policy.state_dict().items():
        h.update(name.encode())
        h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


class McwCredit(m.ProgressReward):
    def award(self, *args):
        return 3 * super().award(*args)


def environment(stage, arm, seed, folder):
    env = make(stage, "A0_prep_only" if arm == "B0" else "A0_no_lc_cost", seed, folder)
    env.use_prep_reward = arm == "B1"
    # McwEnv resets credits on every SUMO reset.
    reset = env.reset
    def start(*args, **kwargs):
        result = reset(*args, **kwargs)
        if env.use_prep_reward:
            env.credits = McwCredit()
        return result
    env.reset = start
    assert not env.use_route_conn and not env.lc_safety_enabled and not env.variants
    assert env.rw["lane_change_penalty"] == env.rw["invalid_action_penalty"] == 0
    assert env.rw["collision_penalty"] == 15
    return env


def first(env, route):
    path = env.routes[route]
    return next(((j, a, b) for j,(a,b) in enumerate(zip(path,path[1:])) if (a,b) in env.signs), None)


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if any(OUT.glob("*/episodes.jsonl")):
        raise RuntimeError("Active experiment output already contains training episodes")
    settings = {}
    for stage in STAGES:
        env = environment(stage, "B0", 11, OUT/"configs")
        cfg = OUT/"configs"/stage
        flows = ET.parse(cfg/"highway.rou.xml").findall("flow")
        demand = sum(int(f.get("number"))*3600/(float(f.get("end"))-float(f.get("begin"))) for f in flows)
        assert demand == {"none":0,"low":3000,"high_real_ratio":15000}[stage]
        settings[stage] = dict(config=str(cfg/"run.sumocfg"), demand=demand, warmup=env.warmup_steps,
            hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in cfg.iterdir() if f.is_file()})
    pairs = []
    for a,b in itertools.combinations(m.ROUTES,2):
        fa,fb = first(env,a),first(env,b)
        if not fa or not fb or fa[:2]!=fb[:2] or env.routes[a][:fa[0]+1]!=env.routes[b][:fb[0]+1]:
            continue
        if fa[1] in ic.RAMPS or (fa[2] in ic.RAMPS)==(fb[2] in ic.RAMPS):
            continue
        ex,main=(a,b) if fa[2] in ic.RAMPS else (b,a)
        pairs.append(dict(exit=ex,main=main,edge=fa[1],exit_next=first(env,ex)[2],main_next=first(env,main)[2],
            exit_lanes=sorted(env.links[fa[1]][first(env,ex)[2]]),main_lanes=sorted(env.links[fa[1]][first(env,main)[2]])))
    assert any(p["exit"]=="route_13" and p["main"]=="route_16" for p in pairs)
    save(OUT/"design.json", dict(stages=settings,pairs=pairs,ppo={k:v.default for k,v in inspect.signature(m.PPO).parameters.items() if v.default!=inspect.Parameter.empty and k not in ("seed","buffer")}|HP,
        start="position 0, max speed, lane 0/1 where available",selection="high paired fraction, arrivals, fewer collisions, earliest checkpoint; per arm and seed",
        seeds=dict(selection=[810000,810001],held_out=[910000,910001,910100,910101]),reward=env.rw,
        sources={str(f.relative_to(m.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [m.ROOT/"utils/experiment_a.py",m.ROOT/"utils/mcw_train.py",m.ROOT/"utils/experiment_b.py"]}))
    for seed in (11,22,33):
        hashes=[]
        for arm in ("B0","B1"):
            folder=OUT/f"{arm}_{seed}"
            folder.mkdir(exist_ok=True)
            agent=agent_for(seed)
            assert agent.num_timesteps==0 and not agent.optimizer.state
            agent.save(str(folder/"policy_0.pt"))
            hashes.append(digest(agent))
            save(folder/"initial.json",dict(seed=seed,policy_sha256=hashes[-1]))
        assert hashes[0]==hashes[1]
    for arm in ("B0","B1"):
        env=environment("none",arm,11,OUT/"configs")
        try:
            samples=[]
            for route in ("route_13","route_16"):
                env.ego_depart_lane="1"
                obs,_=env.reset(seed=710000,options={"route":route})
                traci.vehicle.moveTo(env.ego_id,"86198728_1",traci.lane.getLength("86198728_1")-80)
                obs=env._get_obs()
                samples.append(obs.tolist())
                assert len(obs)==38 and traci.vehicle.getSpeedMode(env.ego_id)==0 and traci.vehicle.getLaneChangeMode(env.ego_id)==0
            assert [i for i,(a,b) in enumerate(zip(*samples)) if a!=b]==[34]
            save(OUT/f"input_check_{arm}.json",samples)
        finally:
            env.close()


class Episodes:
    def __init__(self,env,seed,folder):
        self.env,self.seed,self.folder=env,seed,folder
        self.n=0
        self.order=[]
    def reset(self):
        block,idx=divmod(self.n,16)
        if idx==0:
            self.order=list(m.ROUTES)
            random.Random(self.seed*100000+block).shuffle(self.order)
        route=self.order[idx]
        sim_seed=self.seed*1000000+self.n
        lane=min(block%2,self.env.counts[self.env.routes[route][0]]-1)
        self.env.ego_depart_lane=str(lane)
        obs,info=self.env.reset(seed=sim_seed,options={"route":route})
        with (self.folder/"episodes.jsonl").open("a") as f:
            print(json.dumps([self.n,route,sim_seed,self.env.snapshot[1],traci.vehicle.getLanePosition(self.env.ego_id),self.env.snapshot[7]]),file=f)
        self.n+=1
        return obs,info
    def step(self,action):
        return self.env.step(action)


def train(job):
    arm,seed=job
    if (OUT/f"{arm}_{seed}"/"episodes.jsonl").exists():
        raise RuntimeError("This training directory already contains a run")
    torch.set_num_threads(1)
    folder=OUT/f"{arm}_{seed}"
    agent=agent_for(seed)
    assert digest(agent)==json.loads((folder/"initial.json").read_text())["policy_sha256"]
    env=environment("high_real_ratio",arm,seed,folder/"train")
    try:
        episodes=Episodes(env,seed,folder)
        obs,_=episodes.reset()
        stats=[0.,0]
        for target in list(STEPS)[1:]:
            while agent.num_timesteps<target:
                obs,last,_=agent.collect_rollout(episodes,obs,ep_stats=stats,steps=min(2048,target-agent.num_timesteps))
                adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                agent.update(adv,ret)
                save(folder/"progress.json",dict(steps=agent.num_timesteps,episodes=episodes.n))
            tmp=folder/f"pending_{target}.pt"
            agent.save(str(tmp))
            tmp.replace(folder/f"policy_{target}.pt")
    finally:
        env.close()


if __name__=="__main__":
    torch.set_num_threads(1)
    if sys.argv[1]=="prepare":
        prepare()
    elif sys.argv[1]=="train":
        with ProcessPoolExecutor(6) as pool:
            list(pool.map(train,itertools.product(("B0","B1"),(11,22,33))))


"""Restartable IC experiment campaign. Run from the team repository root."""
import json
import os
import shutil
import subprocess
import time
import hashlib
from pathlib import Path
from types import SimpleNamespace
from itertools import product
from statistics import mean

# Opt in only for headless experiment jobs, leaving the GUI on TraCI.
os.environ["IC_LIBSUMO"] = "1"
import numpy as np
import torch
from env.ic_experiment import ICExperimentEnv
from env.road_builder import build
from train import ROAD, EGO, TRAFFIC, SIMULATION, OBSERVATION, ACTION, REWARD, HPARAMS, snapshot_configs
from algorithms.ppo import PPO
from utils.buffer import RolloutBuffer
from utils.logger import RunLogger
from utils.ic_timeout_trace import TimeoutTrace
from collect_pomdp_data import collect, iter_transitions

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "ic_campaign_v2"
SEEDS = (11, 22, 33)
CORE = ("R0", "BLOCK", "GAP", "PREP", "ZIP", "RAMP")
LOADS = {"low": .6, "base": 1., "high": 1.4}

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")
    tmp.replace(path)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def environment(variants, seed, load="base"):
    traffic = dict(TRAFFIC, demo_vehicle=False, vehs_per_hour=LOADS[load]*TRAFFIC["vehs_per_hour"])
    cfg = OUT/"maps"/load/"highway.sumocfg"
    if not cfg.exists(): build(ROAD,EGO,traffic,str(cfg.parent))
    # Let SUMO choose an insertable route-compatible lane and safe starting speed.
    ego=dict(EGO,depart_lane="best",depart_speed="max")
    return ICExperimentEnv(str(cfg),ROAD,ego,SIMULATION,OBSERVATION,ACTION,REWARD,traffic,variants,seed)

def evaluate(agent, variants, seeds, loads):
    rows = []
    for load in loads:
        env = environment(variants,11,load)
        try:
            for route,seed in product(ROAD["routes"],seeds):
                obs,_ = env.reset(seed=seed,options={"route":route})
                changes = prep = ready = opportunities = compliant = ramp_steps = over_steps = 0
                route_checks = route_ready = 0
                reward_sums = dict(base=0., route=0., zipper=0., ramp=0.)
                reward_counts = dict(base=0, route=0, zipper=0, ramp=0)
                peak = 0.
                trace = TimeoutTrace()
                while True:
                    if env.step_count % 5 == 0: trace.sample(env)
                    obs,_,done,cut,info = env.step(agent.predict(obs,deterministic=True))
                    event=info["ic_event"]
                    for key, value in event.get("reward_components", {}).items():
                        reward_sums[key] += value
                        reward_counts[key] += int(value != 0)
                    if event.get("route_lane_ready") is not None:
                        route_checks += 1
                        route_ready += int(event["route_lane_ready"])
                    changes += int(info["lane_after"] is not None and info["lane_before"] != info["lane_after"])
                    if event["prep100"] is not None:
                        prep+=1; ready+=int(event["prep100"])
                    if event["zipper_compliant"] is not None:
                        opportunities+=1; compliant+=event["zipper_compliant"]
                    ramp_steps+=int(event["ramp"]); over_steps+=int(event["ramp_excess_mps"]>0)
                    peak=max(peak,event["ramp_excess_mps"])
                    if done or cut: break
                rows.append(dict(route=route,seed=seed,load=load,arrival=info["arrived"],
                          collision=info["collided"],timeout=cut and not done,wrong_exit=event["wrong_exit"],
                          seconds=env.step_count*env.step_length,changes=changes,prep=prep,ready=ready,
                          zipper=opportunities,compliant=compliant,ramp_steps=ramp_steps,
                          over_steps=over_steps,peak_excess_mps=peak,
                          route_checks=route_checks,route_ready=route_ready,
                          reward_sums=reward_sums,reward_counts=reward_counts,
                          timeout_diagnostic=trace.result() if cut and not done else None))
        finally: env.close()
    return rows

def rates(rows):
    return {k:mean(float(r[k]) for r in rows) for k in ("arrival","collision","timeout","wrong_exit")}

class Checkpoints(RunLogger):
    def __init__(self, directory, agent, budget):
        super().__init__(str(directory))
        self.directory, self.agent, self.budget = directory, agent, budget
        self.next_checkpoint = min(20_000,budget)
    def log_train(self,step,metrics,verbose=True):
        super().log_train(step,metrics,verbose=False)
        save(self.directory/"progress.json",dict(steps=step,target=self.budget))
        if step >= self.next_checkpoint or step == self.budget:
            self.agent.save(str(self.directory/f"policy-{step}.pt"))
            self.save_csv()
            self.next_checkpoint += 20_000

def train_run(name, variants, seed, budget, lr=None, gamma=None, final_only=False):
    key=f"{name}-{seed}-{budget}"
    directory=OUT/"runs"/key
    marker=directory/"complete.json"
    if marker.exists(): return json.loads(marker.read_text(encoding="utf8"))
    directory.mkdir(parents=True,exist_ok=True)
    env=environment(variants,seed)
    env.load_paths={k:environment(variants,seed,k).cfg_path for k in LOADS}
    env.load_schedule=[]
    hp=dict(HPARAMS,seed=seed,device="cpu")
    if lr is not None: hp["lr"]=lr
    if gamma is not None: hp["gamma"]=gamma
    agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,buffer=RolloutBuffer(),**hp)
    snapshot_configs(str(directory))
    manifest=dict(id=key,variants=sorted(variants),seed=seed,budget=budget,hp=hp,
                  map_sha256=digest(Path(env.cfg_path).with_name("highway.net.xml")),
                  git=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
                  schema="31 base + 6 route/merge features")
    save(directory/"manifest.json",manifest)
    policy=directory/"model.pt"
    started=time.monotonic()
    log=Checkpoints(directory,agent,budget)
    try:
        if not policy.exists():
            agent.learn(env,budget,logger=log,eval_interval=0,exact_budget=True)
            agent.save(str(directory/"model.tmp"))
            (directory/"model.tmp").replace(policy)
            save(directory/"timing.json",dict(training_seconds=time.monotonic()-started))
    finally:
        env.close(); log.close()
    # Evaluate saved policies out of process from training state, on identical cases.
    checkpoints=sorted(directory.glob("policy-*.pt"),key=lambda p:int(p.stem.split("-")[-1]))
    if final_only:
        checkpoints = [p for p in checkpoints if p.stem == f"policy-{budget}"]
    final=None
    for path in checkpoints:
        step=int(path.stem.split("-")[-1])
        result=directory/f"eval-{step}.json"
        if not result.exists():
            agent.load(str(path))
            rows=evaluate(agent,variants,range(1001,1006) if budget>=200000 else [1001],["base"])
            save(result,dict(step=step,rates=rates(rows),rows=rows))
        final=json.loads(result.read_text(encoding="utf8"))
    if final is None or final["step"]!=budget: raise RuntimeError("Missing final checkpoint")
    summary=dict(**manifest,**final["rates"],training_seconds=json.loads((directory/"timing.json").read_text())["training_seconds"])
    save(marker,summary)
    return summary

def collect_shard(directory, label, model, variants, seed, episodes):
    directory.mkdir(parents=True,exist_ok=True)
    metadata=directory/(label+".json")
    if metadata.exists(): return json.loads(metadata.read_text(encoding="utf8"))["transitions"]
    if shutil.disk_usage(directory).free < 12*1024**3: raise RuntimeError("Less than 12 GiB available")
    npz=directory/(label+".npz")
    lines=directory/(label+".jsonl.gz")
    args=SimpleNamespace(seed=seed,workers=1,policy="ppo" if model else "keep-lane",model=str(model) if model else None,
                         device="cpu",stochastic=False,gui=False,ndigits=4,episodes=episodes)
    n=collect(args,None,list(range(episodes)),0,str(lines),str(npz),
              env_factory=lambda:environment(variants,seed))
    with np.load(npz,allow_pickle=False) as d:
        assert all(len(d[k])==n for k in ("observation","action_raw","reward","next_observation","episode","t","terminated","truncated","lane_change"))
        assert d["detected_offsets"][-1]==len(d["detected_xy"])
        assert np.isfinite(d["observation"]).all() and np.isfinite(d["reward"]).all()
        count=0
        for count,record in enumerate(iter_transitions(str(lines)),1):
            assert "next_state" in record and "exit_lane_change_distance_m" in record["event"]
            assert record["episode"]==d["episode"][count-1] and record["t"]==d["t"][count-1]
        assert count==n
    save(metadata,dict(transitions=n,episodes=episodes,seed=seed,model=str(model),npz_sha=digest(npz),
                       jsonl_sha=digest(lines),model_sha=digest(model) if model else None))
    return n

def rank(row):
    return (row["collision"]<.05,row["arrival"],-row["collision"],-row["timeout"])

def campaign():
    OUT.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1)
    def phase(name, **details):
        save(OUT/"status.json",dict(stage=name,**details))
        print(name, details,flush=True)
    phase("pilot-collection")
    collect_shard(OUT/"pilot","pilot",None,(),811,3)
    def experiment(label,variants,seed,budget,**hp):
        phase("PPO",condition=label,seed=seed,steps=budget)
        result=train_run(label,variants,seed,budget,**hp)
        records=[json.loads(p.read_text(encoding="utf8")) for p in (OUT/"runs").glob("*/complete.json")]
        save(OUT/"comparison.json",records)
        return result
    conditions={k:(() if k=="R0" else (k,)) for k in CORE}
    for k,v in conditions.items(): experiment(k,v,11,10000)
    rows={k:experiment(k,v,11,200000) for k,v in conditions.items()}
    improved=[k for k in CORE[1:] if rank(rows[k])>rank(rows["R0"])]
    if len(improved)>1:
        conditions["COMB"]=tuple(improved)
        rows["COMB"]=experiment("COMB",conditions["COMB"],11,200000)
    best=max(rows,key=lambda k:rank(rows[k]))
    variants=conditions[best]
    for seed in SEEDS[1:]:
        experiment("R0",(),seed,200000)
        if best!="R0": experiment(best,variants,seed,200000)
    hps={best:{}, "H-LR":dict(lr=.0001),"H-GAMMA":dict(gamma=.995)}
    means={}
    for name,hp in hps.items():
        repeats=[experiment(name,variants,seed,200000,**hp) for seed in SEEDS]
        means[name]={k:mean(r[k] for r in repeats) for k in ("collision","arrival","timeout")}
    choice=max(means,key=lambda k:rank(means[k]))
    path=OUT/"runs"/f"{choice}-11-200000"/"model.pt"
    phase("held-out-evaluation",model=str(path))
    probe=environment(variants,11);agent=PPO(obs_dim=probe.obs_dim,act_dim=probe.act_dim,**dict(HPARAMS,device="cpu"));probe.close()
    agent.load(str(path))
    rows=evaluate(agent,variants,range(2001,2011),LOADS)
    score=rates(rows)
    save(OUT/"final-evaluation.json",dict(model=str(path),variants=variants,means=means,rates=score,rows=rows))
    if score["arrival"]<.90 or score["collision"]>=.05:
        phase("needs-policy-review",**score);return
    phase("final-collection",model=str(path))
    n=0; shard=0
    while n<10_000_000:
        n+=collect_shard(OUT/"final-data",f"part-{shard:05}",path,variants,300000+shard*100,22)
        shard+=1
        phase("final-collection",transitions=n,shards=shard)
    phase("complete",transitions=n,**score)

if __name__=="__main__":
    import traceback
    try: campaign()
    except Exception:
        save(OUT/"status.json",dict(stage="error",traceback=traceback.format_exc()))
        raise

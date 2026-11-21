"""B1 continuation with identical PPO settings, actions and rewards."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import itertools
import json
import random
import shutil
import sys
import time
from utils.experiment_b import OUT as BASE, Episodes, STAGES, agent_for, digest, environment, m, save, torch
from utils.experiment_b_eval import evaluate_episode, initialize, score

OUT=BASE.parent/"experiment_b1_1m"
SEEDS=(11,22,33)
STEPS=tuple(range(600000,1000001,50000))
PAIRS=json.loads((BASE/"design.json").read_text())["pairs"]
HOLD=(920000,920100,920200,920300)
RULE="Compare 600k to 1M on untouched high traffic. Look for paired gains in >=2/3 seeds, both route13-from-1 and route16-from-0, and collision tradeoff. Mixed evidence is inconclusive."

def prepare():
    OUT.mkdir(exist_ok=False)
    save(OUT/"design.json",dict(parent=str(BASE),mode="B1 policy-only continuation, fresh optimizer/RNG and new episode at boundary",train_seeds=SEEDS,steps=STEPS,selection_base=810000,holdout_base=HOLD,rule=RULE))
    for seed in SEEDS:
        src=BASE/f"B1_{seed}"
        dst=OUT/f"B1_{seed}"
        dst.mkdir()
        p=src/"policy_600000.pt"
        shutil.copy2(p,dst/p.name)
        for stage in STAGES:
            f=src/f"select_600000_{stage}.json"
            shutil.copy2(f,dst/f.name)
        save(dst/"parent.json",dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),next_episode=len((src/"episodes.jsonl").read_text().splitlines())))

def train(seed):
    initialize()
    folder=OUT/f"B1_{seed}"
    meta=json.loads((folder/"parent.json").read_text())
    checkpoint=folder/"policy_600000.pt"
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==meta["sha256"]
    assert not (folder/"episodes.jsonl").exists()
    agent=agent_for(seed)
    agent.load(str(checkpoint))
    assert not agent.optimizer.state
    agent.num_timesteps=600000
    env=environment("high_real_ratio","B1",seed,folder/"train")
    try:
        episodes=Episodes(env,seed,folder)
        episodes.n=meta["next_episode"]
        episodes.order=list(m.ROUTES)
        random.Random(seed*100000+episodes.n//16).shuffle(episodes.order)
        obs,_=episodes.reset()
        stats=[0.,0]
        for target in STEPS[1:]:
            while agent.num_timesteps<target:
                obs,last,_=agent.collect_rollout(episodes,obs,ep_stats=stats,steps=min(2048,target-agent.num_timesteps))
                adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                agent.update(adv,ret)
                save(folder/"progress.json",dict(steps=agent.num_timesteps,next_episode=episodes.n))
            tmp=folder/"pending.pt"
            agent.save(str(tmp))
            tmp.replace(folder/f"policy_{target}.pt")
    finally:
        env.close()

def evaluate(job):
    seed,step,stage,kind=job
    folder=OUT/f"B1_{seed}"
    out=folder/f"{kind}_{step}_{stage}.json"
    if out.exists():return
    agent=agent_for(seed)
    agent.load(str(folder/f"policy_{step}.pt"))
    agent.policy.eval()
    before=digest(agent)
    env=environment(stage,"B1",seed,folder/f"eval_{kind}_{step}_{stage}")
    rows=[]
    try:
        for base,lane,route in itertools.product(HOLD if kind=="hold" else (810000,), (0,1),m.ROUTES):
            rows.append(evaluate_episode(env,agent,route,base+lane,lane))
        score(rows,PAIRS)
        assert digest(agent)==before
        save(out,rows)
    finally:env.close()

def evaluations():
    with ProcessPoolExecutor(4,initializer=initialize) as pool:
        for step in STEPS[1:]:
            jobs=list(itertools.product(SEEDS,[step],STAGES,["select"]))
            while jobs:
                ready=[j for j in jobs if (OUT/f"B1_{j[0]}"/f"policy_{step}.pt").exists()]
                if ready:
                    list(pool.map(evaluate,ready))
                    jobs=[j for j in jobs if j not in ready]
                else:time.sleep(15)
        hold=[]
        for seed in SEEDS:
            folder=OUT/f"B1_{seed}"
            scores={s:score(json.loads((folder/f"select_{s}_high_real_ratio.json").read_text()),PAIRS) for s in STEPS}
            best=max(STEPS,key=lambda s:(scores[s][0],*scores[s][2:],-s))
            save(folder/"selection.json",dict(selected=best,scores=scores))
            hold.extend(itertools.product([seed],sorted({600000,1000000,best}),STAGES,["hold"]))
        list(pool.map(evaluate,hold))

if __name__=="__main__":
    if sys.argv[1]=="prepare":prepare()
    elif sys.argv[1]=="train":
        with ProcessPoolExecutor(3) as pool:list(pool.map(train,SEEDS))
    elif sys.argv[1]=="eval":evaluations()

"""Paired route-16 behavior and all-route outcome counts at each completed evaluation."""
from collections import Counter
import json
import time
from utils.experiment_a import ROOT, STAGES, SIZE, make, m, torch
from utils.run_experiment_a import save

def measure(arm, seed, mark):
    folder = ROOT / f"{arm}_{seed}"
    rows = json.loads((folder / f"eval_{mark}.json").read_text())
    stage = STAGES[(mark-1)//200000]
    env = make(stage,arm,seed,folder/"route16_audit_maps")
    agent = m.PPO(obs_dim=SIZE,act_dim=2,buffer=m.RolloutBuffer(),seed=seed,device="cpu",
                  hidden_sizes=(256,256),n_steps=2048,n_epochs=10,minibatch_size=64,
                  lr=.0001,lane_entropy_coef=.002,lane_keep_bias=1.)
    agent.load(str(folder/f"policy_{mark}.pt"))
    cases=[]
    try:
        for row in rows:
            if row["route"]!="route_16":continue
            obs,_=env.reset(seed=row["seed"],options={"route":"route_16"})
            stats=Counter()
            dst=None
            while True:
                edge,lane,path,k,*_=env.snapshot
                if edge=="86198728":dst=path[k+1]
                obs,_,done,cut,info=env.step(agent.predict(obs))
                post=env.snapshot
                if edge=="86198728":
                    stats["observed_approach"]=1
                    if info["lane_change"]==1:stats["left_requests"]+=1
                    if post and post[0]==edge and post[1]>lane:stats["actual_left"]+=1
                if post and dst and post[0]==dst:stats["passed"]=1
                if done or cut:
                    outcome="collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                    assert outcome==row["outcome"]
                    cases.append(dict(seed=row["seed"],outcome=outcome,**{s:stats[s] for s in ("observed_approach","left_requests","actual_left","passed")},miss_penalties=env.events["missed_split_penalties"]))
                    break
    finally:env.close()
    return dict(outcomes=Counter(r["outcome"] for r in rows),route16=cases)

if __name__=="__main__":
    import sys
    seed=int(sys.argv[1])
    torch.set_num_threads(1)
    arms=("A0_no_lc_cost","A0_missed_split")
    for mark in range(50000,600001,50000):
        result=ROOT/f"A0_missed_split_{seed}"/f"paired_{mark}.json"
        if result.exists():continue
        while not all((ROOT/f"{arm}_{seed}"/f"eval_{mark}.json").exists() for arm in arms):time.sleep(20)
        save(result,{arm:measure(arm,seed,mark) for arm in arms})

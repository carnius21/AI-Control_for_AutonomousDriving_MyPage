"""Extend a matched front-risk trial when initial gains do not persist."""
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from time import sleep
from utils.front_trials import OUT,PARENT,ARMS,MARKS,setup,evaluate,torch
from utils.run_experiment_a import save

EXTRA=(75000,100000,150000)


def results(arm,mark):
    from collections import Counter
    rows=json.loads((OUT/arm/f"eval_{mark}.json").read_text())
    assert len(rows)==48
    c=Counter()
    for r in rows:
        c[r["outcome"]]+=1
        c[r["kind"]]+=1
        c.update(r["metrics"])
    return c


def improved(arm,mark):
    a,b=results("control",mark),results(arm,mark)
    return (b["front"]<a["front"] and b["collision"]<=a["collision"] and b["arrival"]>=a["arrival"] and
            b["timeout"]<=a["timeout"] and b["decelerated"]/max(1,b["response_observed"])>=a["decelerated"]/max(1,a["response_observed"]))


def extend(arm):
    folder,env,agent=setup(arm,"resume_replay_map")
    agent.load(str(PARENT))
    try:
        obs,_=env.reset()
        ep=[0.,0]
        targets=sorted(set(range(10000,150001,10000)) | set(EXTRA))
        for target in targets:
            while agent.num_timesteps<target:
                obs,last,_=agent.collect_rollout(env,obs,steps=min(2048,target-agent.num_timesteps),ep_stats=ep)
                adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                agent.update(adv,ret)
            if target in MARKS:
                reference=torch.load(folder/f"policy_{target}.pt",map_location="cpu")
                assert all(torch.equal(v,reference[k]) for k,v in agent.policy.state_dict().items()),(arm,target,"replay mismatch")
            if target in EXTRA:
                tmp=folder/f"staging_{target}.pt"
                agent.save(str(tmp))
                tmp.replace(folder/f"policy_{target}.pt")
            save(folder/"extension_progress.json",dict(steps=target,replay=target<=50000))
    finally:
        env.close()


def main():
    while not all((OUT/a/f"eval_{k}.json").exists() for a in ARMS for k in MARKS):
        sleep(5)
    persistent=[a for a in ("gap","brake") if all(improved(a,k) for k in (40000,50000))]
    save(OUT/"extension_decision.json",dict(sustained=persistent,extend=not persistent,checkpoints=EXTRA))
    if persistent:
        return
    with ProcessPoolExecutor(max_workers=3) as pool,ProcessPoolExecutor(max_workers=3) as ev:
        runs=[pool.submit(extend,a) for a in ARMS]
        pending=[(a,k) for k in EXTRA for a in ARMS];evaluations=[]
        while pending:
            for f in runs+evaluations:
                if f.done():f.result()
            for job in pending.copy():
                if (OUT/job[0]/f"policy_{job[1]}.pt").exists():
                    evaluations.append(ev.submit(evaluate,job))
                    pending.remove(job)
            sleep(2)
        for f in runs+evaluations:f.result()
    save(OUT/"extended_complete.json",dict(steps=EXTRA,arms=ARMS))


if __name__=="__main__":
    main()

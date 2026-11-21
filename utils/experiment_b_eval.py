"""Read-only checkpoint evaluation in processes separate from rollout collection."""
from concurrent.futures import ProcessPoolExecutor
import csv
import itertools
import json
import time
from utils.experiment_b import OUT, STEPS, STAGES, agent_for, digest, environment, first, m, save, torch, traci


def evaluate_episode(env, agent, route, sim_seed, lane):
    path=env.routes[route]
    env.ego_depart_lane=str(min(lane,env.counts[path[0]]-1))
    obs,_=env.reset(seed=sim_seed,options={"route":route})
    start=[env.snapshot[0],env.snapshot[1],traci.vehicle.getLanePosition(env.ego_id),env.snapshot[7],traci.simulation.getTime()]
    forks={}
    for j,(edge,nxt) in enumerate(zip(path,path[1:])):
        if (edge,nxt) in env.signs:
            forks[j]=dict(edge=edge,expected=nxt,actual=None,wrong_entries=0,returns=0,wrong_end_stops=0,
                          targets=sorted(env.links[edge][nxt]),samples={},first_distance=None)
    stopped=False
    was_stopped_edge=None
    previous={}
    while True:
        edge,l,path_now,idx,j,d,sides,speed,rem=env.snapshot
        r=forks.get(idx)
        if r and edge==r["edge"]:
            if "approach_lane" not in r:
                r["approach_lane"]=l
                r["initially_ready"]=l in r["targets"]
            stopped=l not in r["targets"] and rem<=1 and speed<=.1
            if stopped and was_stopped_edge!=edge:
                r["wrong_end_stops"]+=1
            was_stopped_edge=edge if stopped else None
        credit=len(env.credits.paid)
        bonus=env.events["prep_reward"]
        action=agent.predict(obs,deterministic=True)
        sample=None
        if j is not None:
            item=forks[j]
            if item["first_distance"] is None:
                item["first_distance"]=float(d)
            thresholds=[t for t in (300,100) if previous.get(j,d)>=t>=d and str(t) not in item["samples"]]
            if thresholds:
                sample=dict(step=env.step_count,distance=d,edge=edge,lane=l,speed=speed,
                    adjacent=sides,current=[env._neighbor(0,leader) for leader in (True,False)])
            previous[j]=d
        obs,_,done,cut,info=env.step(action)
        post=env.snapshot
        payment=env.events["prep_reward"]-bonus + .3*(len(env.credits.paid)-credit)
        change=bool(post and post[0]==edge and post[1]!=l)
        if sample is not None:
            sample.update(accel=float(action[env.accel_index]),command=info["lane_change"],actual_change=change,
                          lane_after=info["lane_after"],prep=payment)
            for t in thresholds:
                item["samples"][str(t)]=sample
        if post and not post[0].startswith(":"):
            for k,decision in forks.items():
                if decision["actual"] is None and post[3]==k+1:
                    decision["actual"]=post[0]
            if r and edge==r["edge"] and change:
                ok=l in r["targets"]
                new=post[1] in r["targets"]
                r["wrong_entries"]+=int(ok and not new)
                r["returns"]+=int(not ok and new)
        if done or cut:
            outcome="collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
            for item in forks.values():
                for t in (300,100):
                    if str(t) not in item["samples"]:
                        initial=item["first_distance"]
                        item["samples"][str(t)]="short_or_entered_view_below_threshold" if initial is not None and initial<t else "not_reached"
            f=first(env,route)
            return dict(route=route,sim_seed=sim_seed,lane_case=lane,start=start,outcome=outcome,
                        first=forks[f[0]] if f else None,forks=forks,last=[edge,l,rem,speed],steps=env.step_count)


def evaluate(job):
    arm,seed,step,stage,hold=job
    folder=OUT/f"{arm}_{seed}"
    prefix="hold" if hold else "select"
    out=folder/f"{prefix}_{step}_{stage}.json"
    if out.exists(): return
    agent=agent_for(seed)
    agent.load(str(folder/f"policy_{step}.pt"))
    agent.policy.eval()
    before=digest(agent)
    env=environment(stage,arm,seed,folder/f"evaluate_{prefix}_{step}_{stage}")
    rows=[]
    try:
        for base in ([910000,910100] if hold else [810000]):
            for lane in (0,1):
                for route in m.ROUTES:
                    rows.append(evaluate_episode(env,agent,route,base+lane,lane))
        assert digest(agent)==before and agent.num_timesteps==0
        save(out,rows)
    finally:
        env.close()


def score(rows,pairs):
    key={(r["route"],r["sim_seed"]):r for r in rows}
    paired=[]
    for p in pairs:
        for s in sorted({r["sim_seed"] for r in rows}):
            a,b=[key[route,s] for route in (p["exit"],p["main"])]
            assert a["start"]==b["start"], (p,s,a["start"],b["start"])
            paired.append(all(r["first"]["actual"]==r["first"]["expected"] for r in (a,b)))
    return (sum(paired),len(paired),sum(r["outcome"]=="arrival" for r in rows),-sum(r["outcome"]=="collision" for r in rows))


def initialize():
    torch.set_num_threads(1)


def run():
    pairs=json.loads((OUT/"design.json").read_text())["pairs"]
    with ProcessPoolExecutor(4,initializer=initialize) as pool:
        for step in STEPS:
            jobs=list(itertools.product(("B0","B1"),(11,22,33),[step],STAGES,[False]))
            while jobs:
                ready=[job for job in jobs if (OUT/f"{job[0]}_{job[1]}"/f"policy_{step}.pt").exists()]
                if ready:
                    list(pool.map(evaluate,ready))
                    jobs=[job for job in jobs if job not in ready]
                else:
                    time.sleep(30)
        held=[]
        for arm,seed in itertools.product(("B0","B1"),(11,22,33)):
            folder=OUT/f"{arm}_{seed}"
            scores={s:score(json.loads((folder/f"select_{s}_high_real_ratio.json").read_text()),pairs) for s in STEPS}
            best=max(STEPS,key=lambda s:(scores[s][0],*scores[s][2:],-s))
            save(folder/"selection.json",dict(selected=best,scores=scores))
            held.extend(itertools.product([arm],[seed],sorted({best,600000}),STAGES,[True]))
        list(pool.map(evaluate,held))
    from utils.experiment_b_report import report
    report()


if __name__=="__main__":
    run()


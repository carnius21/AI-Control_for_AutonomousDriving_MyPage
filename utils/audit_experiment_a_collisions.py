"""Replay collision cases and cross-evaluate saved policies at fixed high demand."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from utils.experiment_a import ROOT, SIZE, make, m, torch, traci
from traci import constants as tc

OUT=ROOT/"collision_and_checkpoints"
VARS=(tc.VAR_LANE_ID,tc.VAR_LANEPOSITION,tc.VAR_SPEED,tc.VAR_POSITION,tc.VAR_ANGLE,tc.VAR_LENGTH)


def evaluate(job):
    arm,step,mode=job
    diagnose=mode=="crashes"
    torch.set_num_threads(1)
    target=OUT/f"{arm}_{step}_{mode}.json"
    if target.exists():
        return
    folder=ROOT/f"{arm}_11"
    original=json.loads((folder/"eval_600000.json").read_text())
    cases=[(r["route"],r["seed"]) for r in original if r["outcome"]=="collision"] if diagnose else [(r,63001+i) for i,r in enumerate(m.ROUTES)]
    if mode=="high48":
        cases=[(r["route"],r["seed"]) for r in original]
    env=make("high_real_ratio",arm,11,OUT/"maps"/target.stem)
    agent=m.PPO(obs_dim=SIZE,act_dim=2,buffer=m.RolloutBuffer(),seed=11,device="cpu",hidden_sizes=(256,256))
    agent.load(str(folder/f"policy_{step}.pt"))
    records=[]
    try:
        for route,seed in cases:
            obs,_=env.reset(seed=seed,options={"route":route})
            if diagnose:
                traci.vehicle.subscribeContext(env.ego_id,tc.CMD_GET_VEHICLE_VARIABLE,75,VARS)
            frames=deque(maxlen=26)
            while True:
                act=agent.predict(obs,deterministic=True)
                if diagnose:
                    edge,lane,_,_,_,_,sides,speed,_=env.snapshot
                    neighbors=traci.vehicle.getContextSubscriptionResults(env.ego_id) or {}
                    ids={v:[data[k] for k in VARS] for v,data in neighbors.items() if all(k in data for k in VARS)}
                    v=traci.vehicle
                    ids[env.ego_id]=[v.getLaneID(env.ego_id),v.getLanePosition(env.ego_id),speed,v.getPosition(env.ego_id),v.getAngle(env.ego_id),v.getLength(env.ego_id)]
                    state=dict(t=traci.simulation.getTime(),vehicles=ids,obs=obs.tolist(),sides=sides,leader=v.getLeader(env.ego_id,env.visibility),
                               attempt_before=env.events["attempts"],risk_before=env.events["risk_attempts"])
                obs,_,done,cut,info=env.step(act)
                if diagnose:
                    for key in ("accel_raw","lane_change","lane_change_applied","lane_before","lane_after"):
                        state[key]=info[key]
                    state["attempt"]=env.events["attempts"]-state.pop("attempt_before")
                    state["risk"]=env.events["risk_attempts"]-state.pop("risk_before")
                    frames.append(state)
                if done or cut:
                    outcome="collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                    record=dict(route=route,seed=seed,outcome=outcome)
                    if diagnose:
                        assert outcome=="collision",(arm,route,seed,outcome)
                        collisions=[dict(type=c.type,collider=c.collider,victim=c.victim,lane=c.lane,pos=c.pos,colliderSpeed=c.colliderSpeed,victimSpeed=c.victimSpeed) for c in traci.simulation.getCollisions() if env.ego_id in (c.collider,c.victim)]
                        record.update(collisions=collisions,ego=env.ego_id,time=traci.simulation.getTime())
                        with gzip.open(OUT/f"{arm}_{route}_{seed}.json.gz","wt") as f:
                            json.dump(list(frames),f)
                    records.append(record)
                    break
        target.write_text(json.dumps(records,indent=2))
    finally:
        env.close()


if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    jobs=[(a,600000,"crashes") for a in ("A2","A3")]
    jobs += [(a,s,"high16") for s in (600000,400000,200000,350000,250000,300000,150000,100000,50000) for a in ("A2","A3")]
    if "--paired48" in __import__("sys").argv:
        jobs=[(a,s,"high48") for s in (400000,500000,550000,450000) for a in ("A2","A3")]
    with ProcessPoolExecutor(max_workers=6) as pool:
        list(pool.map(evaluate,jobs))


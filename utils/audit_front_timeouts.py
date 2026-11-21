"""Replay every timeout of the selected high-traffic 100k continuation."""
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from utils.front_trials import OUT, setup, traci

DEST=OUT/"timeout_audit_100000"


def run(case):
    route,seed=case
    f,env,agent=setup("brake",str(DEST/"maps"/str(seed)))
    agent.load(str(f/"policy_100000.pt"))
    rows=[]
    try:
        obs,_=env.reset(seed=seed,options={"route":route})
        for i in range(3000):
            edge,lane,path,idx,j,d,sides,speed,rem=env.snapshot
            nxt=path[idx+1] if idx+1<len(path) else None
            targets=sorted(env.links[edge].get(nxt,())) if not edge.startswith(":") and nxt else []
            v=traci.vehicle;ego=env.ego_id;lid=v.getLaneID(ego); pos=v.getLanePosition(ego)
            physical=[]
            for other in traci.lane.getLastStepVehicleIDs(lid):
                delta=v.getLanePosition(other)-pos
                if other!=ego and delta>=0 and delta<65:
                    physical.append((delta-v.getLength(other),v.getSpeed(other),other))
            act=agent.predict(obs,deterministic=True)
            cmd=float(act[env.accel_index])
            request=max(0,min(env.vmax,speed+.2*cmd*(env.max_accel if cmd>=0 else env.max_decel)))
            rec=dict(i=i,edge=edge,lane=lane,nxt=nxt,targets=targets,split=len(env.links[edge])>1,rem=rem,spd=speed,
                     obs=obs.tolist(),lead=env.lead,phys=min(physical) if physical else None,acc=cmd,req=request,
                     lead_speed=v.getSpeed(env.lead[0]) if env.lead and env.lead[0] else None,
                     legal=sorted(env.solid) if i==0 else None)
            obs,_,done,cut,info=env.step(act)
            rec.update(lc=info["lane_change"],accepted=info["lane_change_applied"],post=env.snapshot[7] if env.snapshot else None)
            rows.append(rec)
            if done or cut:
                assert cut and not done and i==2999
                break
        with gzip.open(DEST/f"{route}_{seed}.json.gz","wt",compresslevel=2) as trace:
            json.dump(rows,trace)
    finally:
        env.close()


if __name__=="__main__":
    DEST.mkdir(parents=True,exist_ok=True)
    rows=json.loads((OUT/"brake"/"eval_100000.json").read_text())
    cases=[(r["route"],r["seed"]) for r in rows if r["outcome"]=="timeout"]
    assert len(cases)==18
    with ProcessPoolExecutor(max_workers=6) as pool:list(pool.map(run,cases))

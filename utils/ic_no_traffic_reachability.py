"""B0 diagnostic: route-guided actions through unchanged env.step, no training."""
import json
import subprocess
import numpy as np
from utils.ic_no_traffic_check import DEST, ROUTES, OUT, digest, save, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD, TRAFFIC, ICExperimentEnv, traci, TimeoutTrace

def main():
    mapdir=DEST/'map'
    assert digest(mapdir/'highway.net.xml')==digest(OUT/'maps/base/highway.net.xml')
    for route in ROUTES:
        target=DEST/'b_cases'/(route+'.json')
        if target.exists(): continue
        save(DEST/'status.json',dict(stage='running_B0',route=route,A0_cases=9))
        env=ICExperimentEnv(str(mapdir/'highway.sumocfg'),ROAD,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,demo_vehicle=False,vehs_per_hour=0),(),11)
        try:
            env.reset(seed=1001,options={'route':route})
            trace=TimeoutTrace(); rejected=0; requested=0
            td=DEST/'b_traces';td.mkdir(exist_ok=True)
            with (td/(route+'.jsonl')).open('w',encoding='utf8') as stream:
                while True:
                    assert set(traci.vehicle.getIDList()) <= {env.ego_id}
                    context=env.context()
                    speed=traci.vehicle.getSpeed(env.ego_id)
                    delta=context[2]-speed
                    scale=env.max_accel if delta>=0 else env.max_decel
                    action=np.array([np.clip(delta/(scale*env.step_length),-1,1),np.sign(context[6])],dtype=np.float32)
                    if env.step_count%5==0: trace.sample(env)
                    _,_,done,cut,info=env.step(action)
                    requested+=int(action[1]!=0)
                    rejected+=int(action[1]!=0 and not info.get('lane_change_applied',False))
                    stream.write(json.dumps(dict(t=env.step_count*env.step_length,context=context,action=action.tolist(),lane_before=info.get('lane_before'),lane_after=info.get('lane_after'),applied=info.get('lane_change_applied')))+'\n')
                    if done or cut: break
            save(target,dict(route=route,controller='diagnostic_best_lane_offset',simulation_seed=1001,arrival=bool(info['arrived']),collision=bool(info['collided']),timeout=bool(cut and not done),seconds=env.step_count*env.step_length,requested_lane_changes=requested,rejected_lane_changes=rejected,diagnostic=trace.result() if cut else None,network_sha256=digest(mapdir/'highway.net.xml'),git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
        finally: env.close()
    save(DEST/'status.json',dict(stage='B0_complete',A0_cases=9,B0_cases=3,next='Review reachability evidence before A1 or training'))
if __name__=='__main__': main()

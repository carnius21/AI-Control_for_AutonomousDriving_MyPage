"""Paired start-condition and read-only observation diagnosis; no training."""
import json, subprocess
from collections import defaultdict
from utils.check_toegyewon_only import *
DEST=ROOT/'results/toegyewon_start_v1'
TARGETS=('route_04','route_14')

def run():
 torch.set_num_threads(1)
 for route in TARGETS:
  starts=[(str(lane),speed) for lane in range(len(EDGES[MAN['routes'][route][0]].findall('lane'))) for speed in ('0','10','max')]+[('best','max')]
  for lane,speed in starts:
   for seed in (11,22,33,0):
    name=f'{route}-lane{lane}-speed{speed}-'+(f'R0-{seed}' if seed else 'diagnostic')
    target=DEST/'cases'/(name+'.json')
    if target.exists():
     cached=json.loads(target.read_text())
     assert cached['network_sha256']==digest(MAP/'network.net.xml')
     continue
    save(DEST/'status.json',dict(stage='running',case=name))
    env=ic.ICExperimentEnv(str(MAP/'review.sumocfg'),ROAD_NEW,dict(EGO,depart_lane=lane,depart_speed=speed),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),(),11)
    row=dict(case=name,route=route,training_seed=seed,depart_lane=lane,depart_speed=speed,depart_position=0,**stamp())
    try:
     if seed:
      modeldir=OUT/'runs'/f'R0-{seed}-200000';meta=json.loads((modeldir/'complete.json').read_text())
      agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp']);agent.load(str(modeldir/'policy-200000.pt'));row['policy_sha256']=digest(modeldir/'policy-200000.pt')
     try:obs,_=env.reset(seed=1001,options={'route':route})
     except RuntimeError as exc:
      if '삽입 실패' not in str(exc):raise
      row.update(arrival=False,collision=False,timeout=False,insertion_failure=True,error=str(exc));save(target,row);continue
     row['actual_start']=dict(lane=traci.vehicle.getLaneIndex(env.ego_id),speed=traci.vehicle.getSpeed(env.ego_id),position=traci.vehicle.getLanePosition(env.ego_id),edge=traci.vehicle.getRoadID(env.ego_id))
     trace=TimeoutTrace();teleports=0;stats={};td=DEST/'traces';td.mkdir(exist_ok=True)
     with (td/(name+'.jsonl')).open('w',encoding='utf8') as f:
      while True:
       assert set(traci.vehicle.getIDList())=={env.ego_id}
       ctx=env.context();edge,current,limit,distance,split,offset,best=ctx
       idx=traci.vehicle.getRouteIndex(env.ego_id);path=MAN['routes'][route];nxt=path[idx+1] if idx+1<len(path) else None
       allowed=sorted(env.links.get(edge,{}).get(nxt,()))
       wrong=bool(allowed) and current not in allowed
       desired=int(np.sign(min(allowed,key=lambda x:abs(x-current))-current)) if wrong else 0
       if seed:action=agent.predict(obs,deterministic=True)
       else:
        delta=limit-traci.vehicle.getSpeed(env.ego_id)
        action=np.array([np.clip(delta/((env.max_accel if delta>=0 else env.max_decel)*env.step_length),-1,1),np.sign(best)],dtype=np.float32)
       command=int(env._quantize_lane_change(float(action[1])))
       remaining=traci.lane.getLength(traci.vehicle.getLaneID(env.ego_id))-traci.vehicle.getLanePosition(env.ego_id)
       snapshot=dict(t=env.step_count*.2,edge=edge,lane=current,remaining=remaining,next_edge=nxt,allowed=allowed,desired=desired,context=ctx,observation=obs.tolist(),action=action.tolist(),command=command)
       if env.step_count%5==0:trace.sample(env)
       obs,_,done,cut,info=env.step(action);teleports+=traci.simulation.getStartingTeleportNumber()
       if not edge.startswith(':'):
        s=stats.setdefault(edge,dict(steps=0,wrong_steps=0,moving_wrong_steps=0,best_correct_wrong_steps=0,explicit_guide_missing_wrong_steps=0,toward=0,away=0,hold=0,toward_applied=0,toward_rejected=0,actual_lane_changes=0,allowed=allowed,first=snapshot))
        s['steps']+=1;s['actual_lane_changes']+=int(info.get('lane_after') is not None and info.get('lane_before')!=info.get('lane_after'))
        if wrong:
         s['wrong_steps']+=1;s['moving_wrong_steps']+=int(remaining>10)
         s['best_correct_wrong_steps']+=int(np.sign(best)==desired)
         s['explicit_guide_missing_wrong_steps']+=int(split!=edge or distance is None)
         k='toward' if command==desired else 'hold' if command==0 else 'away';s[k]+=1
         if k=='toward':s['toward_applied' if info.get('lane_change_applied') else 'toward_rejected']+=1
        s['last']=snapshot
       if (env.step_count-1)%5==0:
        snapshot.update(applied=info.get('lane_change_applied'),lane_after=info.get('lane_after'));f.write(json.dumps(snapshot)+'\n')
       if done or cut:break
     row.update(arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),insertion_failure=False,seconds=env.step_count*.2,teleports=teleports,diagnostic=trace.result(),edges=stats)
     save(target,row)
    finally:env.close()
 save(DEST/'status.json',dict(stage='complete',cases=len(list((DEST/'cases').glob('*.json'))),**stamp()))
if __name__=='__main__':run()

"""Paired frozen-policy diagnosis; interventions are NOT retrained PPO results."""
from collections import Counter
from utils.check_toegyewon_only import *
DEST=ROOT/'results/toegyewon_lane_cause_v1'

class ProbeEnv(ic.ICExperimentEnv):
 def _apply_lane_change(self,d):
  v=traci.vehicle;e=v.getRoadID(self.ego_id);i=v.getLaneIndex(self.ego_id)
  if d and e in self.solid: reason='edge_solid_rule'
  elif e.startswith(':'):reason='internal_junction'
  elif not 0<=i+d<traci.edge.getLaneNumber(e):reason='outside_road'
  elif d and self.lc_safety_enabled and v.getLanePosition(self.ego_id)<self.lc_spawn_protect:reason='edge_start_protection'
  elif d and self.lc_safety_enabled and not self._lane_change_is_safe(d):reason='neighbor_safety'
  else:reason='hold' if not d else 'submitted'
  applied=super()._apply_lane_change(d)
  self.command_reason=reason if not applied or reason=='hold' else 'submitted'
  if not applied and reason=='submitted':self.command_reason='traci_rejected'
  return applied

 def context(self):
  ctx=list(super().context())
  if getattr(self,'mode','')!='route_observation':return tuple(ctx)
  v=traci.vehicle;idx=v.getRouteIndex(self.ego_id);path=self.routes[self.episode_route];e=ctx[0]
  if not e.startswith(':') and idx+1<len(path):
   targets=self.links[e].get(path[idx+1],set())
   if targets and len(targets)<self.counts[e]:
    ctx[3]=traci.lane.getLength(v.getLaneID(self.ego_id))-v.getLanePosition(self.ego_id)
    ctx[4]=e;ctx[5]=min(targets,key=lambda x:abs(x-ctx[1]))-ctx[1]
  return tuple(ctx)

 def _lane_connectivity(self,offset):
  base=super()._lane_connectivity(offset)
  if getattr(self,'mode','')!='route_observation' or base<0:return base
  v=traci.vehicle;e=v.getRoadID(self.ego_id);idx=v.getRouteIndex(self.ego_id);path=self.routes[self.episode_route]
  if e.startswith(':') or idx+1>=len(path):return base
  target=self.links[e].get(path[idx+1],set());lane=v.getLaneIndex(self.ego_id)+offset
  if target and lane not in target:
   remaining=traci.lane.getLength(f'{e}_{lane}')-v.getLanePosition(self.ego_id)
   return float(np.clip(remaining/self.visibility,0,1))
  return base

def main():
 torch.set_num_threads(1)
 originals=[json.loads(p.read_text()) for p in sorted((ROOT/'results/toegyewon_only_v2/av').glob('*.json'))]
 failures=[r for r in originals if not r['arrival']]
 assert len(failures)==16
 for mode in ('baseline','route_guidance','route_observation','route_guard'):
  for original in (originals if mode in ('route_guidance','route_guard') else failures):
   route=original['route'];seed=original['training_seed'];key=f'{route}-{seed}-{mode}';target=DEST/'cases'/(key+'.json')
   if target.exists():continue
   save(DEST/'status.json',dict(stage='running',case=key))
   env=ProbeEnv(str(MAP/'review.sumocfg'),ROAD_NEW,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),(),11);env.mode=mode
   modeldir=OUT/'runs'/f'R0-{seed}-200000';meta=json.loads((modeldir/'complete.json').read_text())
   agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp']);agent.load(str(modeldir/'policy-200000.pt'))
   stats={};trace=TimeoutTrace();teleports=0
   try:
    obs,_=env.reset(seed=1001,options={'route':route})
    td=DEST/'traces';td.mkdir(parents=True,exist_ok=True)
    with (td/(key+'.jsonl')).open('w',encoding='utf8') as stream:
     while True:
      assert set(traci.vehicle.getIDList())=={env.ego_id}
      ctx=env.context();edge,lane,limit,dist,split,offset,best=ctx
      v=traci.vehicle;idx=v.getRouteIndex(env.ego_id);path=MAN['routes'][route];nxt=path[idx+1] if idx+1<len(path) else None
      allowed=sorted(env.links.get(edge,{}).get(nxt,()))
      wrong=bool(allowed) and lane not in allowed
      desired=int(np.sign(min(allowed,key=lambda x:abs(x-lane))-lane)) if wrong else 0
      remaining=traci.lane.getLength(v.getLaneID(env.ego_id))-v.getLanePosition(env.ego_id)
      raw=agent.predict(obs,deterministic=True).copy();action=raw.copy()
      if mode=='route_guidance':action[1]=np.sign(best)
      if mode=='route_guard' and allowed:
       proposed=env._quantize_lane_change(float(action[1]))
       if wrong:action[1]=desired
       elif lane+proposed not in allowed:action[1]=0.
      command=env._quantize_lane_change(float(action[1]))
      snapshot=dict(t=env.step_count*.2,edge=edge,lane=lane,next_edge=nxt,allowed=allowed,desired=desired,remaining=remaining,speed=v.getSpeed(env.ego_id),context=ctx,observation=obs.tolist(),policy_action=raw.tolist(),executed_action=action.tolist(),command=command)
      if env.step_count%5==0:trace.sample(env)
      obs,_,done,cut,info=env.step(action);teleports+=traci.simulation.getStartingTeleportNumber()
      same=env.ego_id in v.getIDList() and v.getRoadID(env.ego_id)==edge
      snapshot.update(reason=env.command_reason,submitted=bool(info['lane_change_applied']),lane_after=info['lane_after'],actual_change_same_edge=bool(same and lane!=info['lane_after']))
      if not edge.startswith(':'):
       s=stats.setdefault(edge,dict(first=snapshot,wrong_moving=Counter(),wrong_stopped=Counter(),departures_from_valid_lane=0,correct_submitted_not_moved=0))
       if wrong:
        phase=s['wrong_moving'] if remaining>10 else s['wrong_stopped']
        phase['steps']+=1;phase['guide_missing']+=int(dist is None or split!=edge);phase['best_correct']+=int(np.sign(best)==desired)
        relation='toward' if command==desired else 'hold' if command==0 else 'away'
        phase[relation]+=1;phase[relation+':'+env.command_reason]+=1
        if relation=='toward' and info['lane_change_applied'] and same and lane==info['lane_after']:s['correct_submitted_not_moved']+=1
       if allowed and lane in allowed and same and info['lane_after'] not in allowed:s['departures_from_valid_lane']+=1
       s['last']=snapshot
      if (env.step_count-1)%5==0:stream.write(json.dumps(snapshot)+'\n')
      if done or cut:break
    row=dict(route=route,training_seed=seed,mode=mode,arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,seconds=env.step_count*.2,edges=stats,diagnostic=trace.result(),policy_sha256=digest(modeldir/'policy-200000.pt'),**stamp())
    if mode=='baseline':assert row['arrival']==original['arrival'] and row['collision']==original['collision'] and row['timeout']==original['timeout']
    save(target,row)
   finally:env.close()
 save(DEST/'status.json',dict(stage='complete',cases=128,**stamp()))
if __name__=='__main__':main()

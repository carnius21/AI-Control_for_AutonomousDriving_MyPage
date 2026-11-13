"""Single-axis diagnostic interventions; frozen PPO is never modified."""
from utils.check_toegyewon_only import *
DEST=ROOT/'results/toegyewon_axes_v1'
def main():
 torch.set_num_threads(1)
 for mode in ('lane_only','speed_only'):
  for seed in (11,22,33):
   modeldir=OUT/'runs'/f'R0-{seed}-200000';meta=json.loads((modeldir/'complete.json').read_text())
   for route in ('route_04','route_14'):
    name=f'{route}-{seed}-{mode}';target=DEST/'cases'/(name+'.json')
    if target.exists():continue
    save(DEST/'status.json',dict(stage='running',case=name))
    env=ic.ICExperimentEnv(str(MAP/'review.sumocfg'),ROAD_NEW,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),(),11)
    try:
     agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp']);agent.load(str(modeldir/'policy-200000.pt'))
     obs,_=env.reset(seed=1001,options={'route':route});trace=TimeoutTrace();teleports=0
     while True:
      assert set(traci.vehicle.getIDList())=={env.ego_id}
      ctx=env.context();action=agent.predict(obs,deterministic=True).copy()
      if mode=='lane_only':action[1]=np.sign(ctx[6])
      else:
       delta=ctx[2]-traci.vehicle.getSpeed(env.ego_id)
       action[0]=np.clip(delta/((env.max_accel if delta>=0 else env.max_decel)*env.step_length),-1,1)
      if env.step_count%5==0:trace.sample(env)
      obs,_,done,cut,info=env.step(action);teleports+=traci.simulation.getStartingTeleportNumber()
      if done or cut:break
     save(target,dict(case=name,route=route,training_seed=seed,intervention=mode,arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,seconds=env.step_count*.2,diagnostic=trace.result(),policy_sha256=digest(modeldir/'policy-200000.pt'),**stamp()))
    finally:env.close()
 save(DEST/'status.json',dict(stage='complete',cases=12,**stamp()))
if __name__=='__main__':main()

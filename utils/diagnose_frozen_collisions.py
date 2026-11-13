"""Read-only replay of frozen traffic failures; brake is a labeled diagnostic only."""
from utils import navigation_followup as f
import numpy as np
D=f.ROOT/'results/collision_diagnosis_v1'

def sample(env):
 v=f.base.traci.vehicle;e=env.ego_id
 lead=v.getLeader(e,200);follow=v.getFollower(e,200)
 def other(pair):
  if not pair or not pair[0]:return None
  return dict(id=pair[0],gap_excluding_minGap=float(pair[1]),speed=v.getSpeed(pair[0]))
 return dict(speed=v.getSpeed(e),lane=v.getLaneID(e),pos=v.getLanePosition(e),leader=other(lead),follower=other(follow),minGap=v.getMinGap(e),speedMode=v.getSpeedMode(e),lcMode=v.getLaneChangeMode(e),observed_leader=env._neighbor(0,True))

def run(route,mode,seed,simseed,intervention):
 key=f'{route}-{mode}-{seed}-{simseed}-{intervention}';p=D/(key+'.json')
 if p.exists():return
 source=f.ROOT/f'results/navigation_{route.replace("_","")}_v1/runs/{mode}-{seed}-200000'
 agent=f.base.PPO(obs_dim=37,act_dim=2,**f.read(source/'manifest.json')['hp']);agent.load(str(source/'model.pt'))
 env=f.environment(mode,seed,'low',[route]);steps=[]
 try:
  obs,_=env.reset(seed=simseed,options={'route':route});initial=sample(env)
  for i in range(300):
   before=sample(env);policy=agent.predict(obs,deterministic=True);action=policy.copy()
   if intervention in ('brake','brake_only'):action[0]=-1.
   if intervention in ('brake','hold_lane'):action[1]=0.
   obs_before=obs.tolist()
   target=float(np.clip(before['speed']+float(action[0])* (env.max_accel if action[0]>=0 else env.max_decel)*env.step_length,0,env.vmax))
   obs,reward,done,cut,info=env.step(action)
   after=sample(env) if env.ego_id in f.base.traci.vehicle.getIDList() else None
   collisions=[{k:getattr(c,k,None) for k in ('collider','victim','colliderSpeed','victimSpeed','type','lane','pos')} for c in f.base.traci.simulation.getCollisions()]
   steps.append(dict(t=env.step_count*env.step_length,before=before,observation=obs_before,policy=policy.tolist(),applied=action.tolist(),target_speed=target,actual=after,accel_raw=info['accel_raw'],lane_raw=info['lane_change_raw'],lane_applied=info['lane_change_applied'],collisions=collisions))
   if done or cut:break
  f.save(p,dict(route=route,mode=mode,training_seed=seed,simseed=simseed,intervention=intervention,model_sha=f.base.digest(source/'model.pt'),initial=initial,collision=bool(info['collided']),arrival=bool(info['arrived']),seconds=env.step_count*env.step_length,horizon=60,steps=steps))
 finally:env.close()

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--paired',action='store_true');args=parser.parse_args()
 f.base.torch.set_num_threads(1)
 if args.paired:D=f.ROOT/'results/collision_diagnosis_v2'
 for route in ('route_04','route_14'):
  for mode in ('N0','N1','N2'):
   for seed in ((11,) if args.paired else (11,22,33)):
    for simseed in range(40001,40006):
     for intervention in (('policy','brake_only','hold_lane') if args.paired else ('policy',)):
      run(route,mode,seed,simseed,intervention)
  if not args.paired:
   for simseed in range(40001,40006):run(route,'N0',11,simseed,'brake')
 print('Diagnosis completed; intervention results are not policy performance')

"""Static navigation examples and matched-action integration checks before training."""
from utils.train_navigation_route04 import *

def main():
 # Renumbering: destination lane 0 is reached from upstream lane 2, not lane 0.
 nav=RouteNavigation({'a':3,'b':3,'c':1},[('a','b',0,1),('a','b',1,2),('a','b',2,0),('b','c',0,0)],{'a':100,'b':20,'c':50})
 q=nav.query(['a','b','c'],0,0,50)
 assert q['prepare_targets']==[2] and q['distance']==70
 assert nav.query(['a','b','c'],0,0,301)['distance'] is None
 assert nav.query(['a','b','c'],2,0,10)['distance'] is None
 assert nav.query(['a','b','c'],0,0,50,True)['distance'] is None
 # Multiple compatible lanes; no choice of a single lane when already compatible.
 q=NAV.query(['170059994','1063527748','797789364','781184662#3'],0,3,80)
 assert q['current_targets']==[0,1,2] and NAV.offset(3,q['current_targets'])==-1
 q=NAV.query(['1063527748','797789364','781184662#3'],0,0,100)
 assert q['current_targets']==[2] and NAV.offset(0,q['current_targets'])==2
 q=NAV.query(['86198708','86198708#1','1414146971'],0,0,40)
 assert q['current_targets']==[1,2,3,4] and q['distance']==40
 # Impossible straight connection across two short edges is explicitly ambiguous.
 nav=RouteNavigation({'a':1,'b':2,'c':1},[('a','b',0,0),('b','c',1,0)],{'a':10,'b':5,'c':10})
 assert nav.query(['a','b','c'],0,0,2)['ambiguous']
 checks=[]
 for route in MAN['routes']:
  trajectories=[]
  for mode in ('N0','N1','N2'):
   env=environment(mode,11,route=route)
   try:
    obs,_=env.reset(seed=1001);states=[]
    for t in range(40):
     assert obs.shape==(37,) and np.isfinite(obs).all() and np.max(np.abs(obs))<=1.00001
     action=np.array([.2,(-1,0,1)[t%3]],dtype=np.float32)
     obs,_,done,cut,info=env.step(action)
     assert env.route_override_count==0 and info['policy_action_raw']==info['environment_action_raw']
     states.append((info['lane_after'],round(info['speed'],6)))
     if done or cut:break
    trajectories.append(states)
   finally:env.close()
  assert trajectories[0]==trajectories[1]==trajectories[2],route
  checks.append(dict(route=route,matched_action_steps=len(trajectories[0]),modes=3,overrides=0))
 starts=[]
 for i in range(20):
  env=environment('N0',11,str(i%4),str((i//4)*5))
  try:
   obs,_=env.reset(seed=20001+i);assert env.ego_id in traci.vehicle.getIDList()
   starts.append(dict(seed=20001+i,lane=i%4,speed=(i//4)*5,inserted=True))
  finally:env.close()
 save(DEST/'validation.json',dict(status='passed',static_cases=7,matched_actions=checks,validation_starts=starts,**stamp()))
 print('Static cases passed; 16 routes x 3 modes x 40 identical-action steps; 20 distinct starts inserted')
if __name__=='__main__':main()

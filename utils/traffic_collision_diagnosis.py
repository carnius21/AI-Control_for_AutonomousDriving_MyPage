"""Read-only policy replay with per-step collision evidence."""
import concurrent.futures,json
from utils import traffic_continuation as t
b=t.b;f=t.f
OUT=f.ROOT/'results/traffic_collision_diagnosis_20261113'
def one(spec):
 seed,kind=spec;b.torch.set_num_threads(1)
 d=t.OUT/'runs'/f'low-{seed}';meta=f.read(d/'manifest.json');p=d/('initial.pt' if kind=='initial' else 'model.pt')
 a=b.PPO(obs_dim=47,act_dim=2,**meta['hp']);a.load(str(p));rows=[]
 for route in ['route_01','route_04','route_13','route_14']:
  for simseed in [40001,40002,40003]:
   e=t.env(seed,'low');trace=[]
   try:
    obs,_=e.reset(seed=simseed,options={'route':route})
    while True:
     v=b.traci.vehicle;lead=v.getLeader(e.ego_id,200);speed=v.getSpeed(e.ego_id);act=a.predict(obs,deterministic=True)
     x=dict(step=e.step_count,speed=speed,lane=v.getLaneID(e.ego_id),position=v.getLanePosition(e.ego_id),action=[float(z) for z in act],leader=lead[0] if lead else None,gap=float(lead[1]) if lead else None,leader_speed=v.getSpeed(lead[0]) if lead else None)
     obs,reward,done,cut,info=e.step(act)
     x.update(reward=float(reward),lane_applied=info.get('lane_change_applied'),collided=bool(info['collided']))
     trace.append(x)
     if done or cut:break
    assert e.route_override_count==0
    rows.append(dict(route=route,simulation_seed=simseed,arrival=bool(info['arrived']),collision=bool(info['collided']),seconds=e.step_count*e.step_length,initial=trace[0],last=trace[-20:]))
   finally:e.close()
   t.save(OUT/f'{kind}-{seed}.json',dict(model_sha=b.digest(p),map_sha=b.digest(b.MAP/'network.net.xml'),rows=rows))
 return seed,kind
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:done=list(pool.map(one,[(s,k) for s in [11,22,33] for k in ['initial','final']]))
 t.save(OUT/'status.json',dict(stage='complete',jobs=done))

"""Frozen-model current-map revalidation; bounded parallelism, no training or overrides."""
import os,json,time,argparse,concurrent.futures,subprocess,hashlib,traceback
from pathlib import Path
from utils import train_navigation_clarity as c
f=c.f;b=f.base
OUT=f.ROOT/'results/resume_validation_20261112'
f.OUT=OUT

def save(path,data):
 for attempt in range(20):
  try:return b.save(path,data)
  except PermissionError:
   if attempt==19:raise
   time.sleep(.1)
f.save=save
def sources(mode,seed):
 return (c.OUT/'runs'/f'baseline-{seed}') if mode=='baseline' else f.ROOT/'results/lane_learning_v1/runs'/f'{mode}-{seed}'
def environment(seed,lane,speed,meta):
 return c.ClarityEnv(str(OUT/'traffic_v2/none/run.sumocfg'),dict(b.ROAD_NEW,routes=b.MAN['routes']),dict(meta['ego'],depart_lane=str(lane),depart_speed=str(speed)),meta['simulation'],b.OBSERVATION,meta['action'],meta['reward'],dict(b.TRAFFIC,prefill={'enabled':False}),(),seed,navigation=b.NAV,clarity='baseline')
def execute(job):
 b.torch.set_num_threads(1)
 key=job['key'];target=OUT/'jobs'/key;target.mkdir(parents=True,exist_ok=True)
 if (target/'complete.json').exists():return key
 (target/'error.json').unlink(missing_ok=True)
 save(target/'progress.json',dict(stage='running',pid=os.getpid(),started=time.time(),job=job))
 try:
  if job['kind']=='hv':
   f.state=lambda *args,**kw:None
   passed=f.hv_case(job['load'],job['seed']);save(target/'complete.json',dict(passed=passed));return key
  seed=job['seed'];run=sources(job['mode'],seed);meta=f.read(run/'manifest.json');base_meta=meta.get('baseline_manifest',meta)
  model=run/('model.pt' if job['step']==800000 else f"policy-{job['step']}.pt")
  agent=b.PPO(obs_dim=47,act_dim=2,**meta['hp']);agent.load(str(model))
  save(target/'manifest.json',dict(job=job,model=str(model),model_sha=b.digest(model),training_map_sha=base_meta['hashes']['maps/toegyewon_only/network.net.xml'],evaluation_map_sha=b.digest(b.MAP/'network.net.xml'),commit=b.COMMIT,action_overrides=False,simulation=base_meta['simulation'],action=base_meta['action'],reward=base_meta['reward']))
  rows=[]
  for route in f.ROUTES:
   count=f.COUNTS[b.MAN['routes'][route][0]]
   if job['kind']=='replay':starts=list(dict.fromkeys([('best','max'),('0','5'),('0','15'),(str(count-1),'15')]))
   else:starts=[(str(lane),str(speed)) for speed in [2,7,12,17,22,4,9,14,19,24,1,3,6,8,11,13,16,18,21,23] for lane in range(count)][:20]
   for i,(lane,speed) in enumerate(starts):
    simseed=(50001 if job['kind']=='replay' else 71001)+i
    row=dict(route=route,lane=lane,speed=speed,simulation_seed=simseed,arrival=False,collision=False,timeout=False,insertion_failure=False)
    env=environment(seed,lane,speed,base_meta)
    try:
     try:obs,_=env.reset(seed=simseed,options={'route':route})
     except RuntimeError as exc:
      if '삽입 실패' not in str(exc):raise
      row.update(insertion_failure=True,error=str(exc));rows.append(row);continue
     trace=b.TimeoutTrace();teleports=0
     while True:
      if env.step_count%5==0:trace.sample(env)
      obs,_,done,cut,info=env.step(agent.predict(obs,deterministic=True));teleports+=b.traci.simulation.getStartingTeleportNumber()
      if done or cut:break
     assert env.route_override_count==0
     row.update(arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,seconds=env.step_count*env.step_length,route_overrides=0,diagnostic=trace.result());rows.append(row)
    finally:env.close()
    save(target/'progress.json',dict(stage='evaluating',pid=os.getpid(),completed_cases=len(rows),route=route,updated=time.time()))
   save(target/'partial.json',rows)
  save(target/'evaluation.json',rows)
  save(target/'complete.json',dict(cases=len(rows),arrivals=sum(r['arrival'] for r in rows),collisions=sum(r['collision'] for r in rows),timeouts=sum(r['timeout'] for r in rows),insertion_failures=sum(r['insertion_failure'] for r in rows),per_route_gate=f.gate(rows,f.ROUTES) if job['kind']=='holdout' else None))
  return key
 except Exception as exc:
  save(target/'error.json',dict(error=repr(exc),traceback=traceback.format_exc()));raise

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for load,hv in [('none',False),('low',True),('base',True)]:f.prepare(load,hv)
  assert b.digest(OUT/'traffic_v2/none/network.net.xml')==b.digest(b.MAP/'network.net.xml')
  snapshot={path:b.digest(f.ROOT/path) for path in c.SOURCES}
  save(OUT/'manifest.json',dict(sources=snapshot,commit=b.COMMIT,workers=6,torch_threads=1,forced_correction=False))
  jobs=[]
  for step in [600064,800000]:
   for mode in ['baseline','entropy','reward','combined']:
    for seed in [11,22,33]:jobs.append(dict(key=f'replay-{mode}-{seed}-{step}',kind='replay',mode=mode,seed=seed,step=step))
  for mode in ['baseline','combined']:
   for seed in [11,22,33]:jobs.append(dict(key=f'holdout-{mode}-{seed}-600064',kind='holdout',mode=mode,seed=seed,step=600064))
  for load in ['low','base']:
   for seed in [1001,1002,1003]:jobs.append(dict(key=f'hv-{load}-{seed}',kind='hv',load=load,seed=seed))
  if args.smoke:jobs=jobs[:1]
  completed=[];errors=[]
  with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
   pending={pool.submit(execute,j):j['key'] for j in jobs}
   save(OUT/'status.json',dict(stage='running',pid=os.getpid(),total=len(jobs),completed=completed,errors=errors))
   for future in concurrent.futures.as_completed(pending):
    key=pending[future]
    try:future.result();completed.append(key)
    except Exception as exc:errors.append(dict(job=key,error=repr(exc)))
    save(OUT/'status.json',dict(stage='running',pid=os.getpid(),total=len(jobs),completed=completed,errors=errors,updated=time.time()))
  assert all(b.digest(f.ROOT/path)==value for path,value in snapshot.items()),'Source changed during evaluation'
  save(OUT/'status.json',dict(stage='checks_complete' if not errors else 'error',pid=os.getpid(),total=len(jobs),completed=completed,errors=errors,updated=time.time()))
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

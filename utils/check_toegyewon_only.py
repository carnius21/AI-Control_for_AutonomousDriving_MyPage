"""Frozen-policy and HV passage checks on the isolated OSM map; never trains."""
import argparse, json, subprocess, copy
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from utils.ic_campaign import ROOT, OUT, PPO, torch, save, digest, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD, TRAFFIC
import env.ic_experiment as ic
from env.sumo_env import traci
from utils.ic_timeout_trace import TimeoutTrace
from sumolib import checkBinary
MAP=ROOT/'maps/toegyewon_only';DEST=ROOT/'results/toegyewon_only_v1'
MAN=json.loads((MAP/'manifest.json').read_text())
XML=ET.parse(MAP/'network.net.xml').getroot()
EDGES={e.get('id'):e for e in XML.findall('edge') if not e.get('function')}
# Preserve the original six IC features, remapping only map-dependent ramp membership.
ic.ZIP=()
ic.RAMPS={eid for eid,e in EDGES.items() if e.get('type','').endswith('_link')}
ROAD_NEW=dict(ROAD,routes=MAN['routes'],edges=[(eid,e.get('from'),e.get('to'),len(e.findall('lane'))) for eid,e in EDGES.items()],connections=[(c.get('from'),c.get('to'),int(c.get('fromLane')),int(c.get('toLane'))) for c in XML.findall('connection') if c.get('from') in EDGES and c.get('to') in EDGES],solid_lane_edges=[eid for eid,e in EDGES.items() if any(l.get('changeLeft') or l.get('changeRight') for l in e.findall('lane'))])
COMMIT=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
def stamp():return dict(git=COMMIT,network_sha256=digest(MAP/'network.net.xml'),simulation_seed=1001)
def checked_existing(target):
 if not target.exists():return False
 saved=json.loads(target.read_text())
 if saved['network_sha256']!=digest(MAP/'network.net.xml'):
  raise RuntimeError('Map changed: preserve old results and select a new DEST version before running')
 return True

def hv():
 for route,path in MAN['routes'].items():
  for lane in range(len(EDGES[path[0]].findall('lane'))):
   for ctrl in ('krauss','idm','eidm','acc'):
    key=f'{route}-lane{lane}-{ctrl}';target=DEST/'hv'/(key+'.json')
    if checked_existing(target):continue
    save(DEST/'status.json',dict(stage='H0',case=key))
    traci.start([checkBinary('sumo'),'-c',str(MAP/'review.sumocfg'),'--step-length','.2','--no-step-log','true','--seed','1001','--no-warnings','true'])
    arrived=inserted=False;collision=teleport=0;last={}
    try:
     traci.vehicle.add('probe',route,typeID='car_'+ctrl,departLane=str(lane),departSpeed='0',departPos='0')
     for t in range(4500):
      traci.simulationStep()
      collision+=traci.simulation.getCollidingVehiclesNumber();teleport+=traci.simulation.getStartingTeleportNumber()
      if 'probe' in traci.vehicle.getIDList():
       inserted=True;last=dict(edge=traci.vehicle.getRoadID('probe'),lane=traci.vehicle.getLaneID('probe'),position=traci.vehicle.getLanePosition('probe'),speed=traci.vehicle.getSpeed('probe'))
      if 'probe' in traci.simulation.getArrivedIDList():arrived=True;break
     row=dict(route=route,path=path,controller=ctrl,depart_lane=lane,depart_speed=0,arrival=arrived,collision=bool(collision),teleports=teleport,insertion_failure=not inserted,timeout=inserted and not arrived,seconds=(t+1)*.2,last=last,**stamp())
     save(target,row)
    finally:traci.close()

def av(diagnostic=False):
 torch.set_num_threads(1)
 seeds=(0,) if diagnostic else (11,22,33)
 for seed in seeds:
  modeldir=OUT/'runs'/f'R0-{seed}-200000'
  if not diagnostic:meta=json.loads((modeldir/'complete.json').read_text())
  for route in MAN['routes']:
   key=f'{route}-'+('diagnostic' if diagnostic else f'R0-{seed}');target=DEST/('b' if diagnostic else 'av')/(key+'.json')
   if checked_existing(target):continue
   save(DEST/'status.json',dict(stage='B0' if diagnostic else 'A0',case=key))
   env=ic.ICExperimentEnv(str(MAP/'review.sumocfg'),ROAD_NEW,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),(),11)
   row=dict(route=route,path=MAN['routes'][route],training_seed=seed if not diagnostic else None,controller='diagnostic' if diagnostic else 'R0',**stamp())
   try:
    if not diagnostic:
     agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp']);agent.load(str(modeldir/'policy-200000.pt'));row['policy_sha256']=digest(modeldir/'policy-200000.pt')
    try:obs,_=env.reset(seed=1001,options={'route':route})
    except RuntimeError as exc:
     if '삽입 실패' not in str(exc):raise
     row.update(arrival=False,collision=False,timeout=False,insertion_failure=True,error=str(exc));save(target,row);continue
    trace=TimeoutTrace();teleports=0;requests=rejected=0
    td=DEST/'traces';td.mkdir(exist_ok=True)
    with (td/(key+'.jsonl')).open('w',encoding='utf8') as stream:
     while True:
      assert set(traci.vehicle.getIDList())<={env.ego_id}
      context=env.context()
      if diagnostic:
       delta=context[2]-traci.vehicle.getSpeed(env.ego_id)
       action=np.array([np.clip(delta/((env.max_accel if delta>=0 else env.max_decel)*env.step_length),-1,1),np.sign(context[6])],dtype=np.float32)
      else:action=agent.predict(obs,deterministic=True)
      sampled=env.step_count%5==0
      if sampled:trace.sample(env)
      obs,reward,done,cut,info=env.step(action)
      teleports+=traci.simulation.getStartingTeleportNumber()
      request=bool(info.get('lane_change',0));requests+=request;rejected+=request and not info.get('lane_change_applied',False)
      if sampled:stream.write(json.dumps(dict(t=env.step_count*.2,context=context,action=action.tolist(),lane_before=info.get('lane_before'),lane_after=info.get('lane_after'),applied=info.get('lane_change_applied'),trace=trace.samples[-1] if trace.samples else None))+'\n')
      if done or cut:break
    row.update(arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),wrong_exit=info['ic_event']['wrong_exit'],insertion_failure=False,teleports=teleports,seconds=env.step_count*.2,requested=requests,rejected=rejected,diagnostic=trace.result())
    save(target,row)
   finally:env.close()
def main():
 global DEST
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['hv','av','b']);p.add_argument('--output',type=Path,default=DEST);a=p.parse_args()
 DEST=a.output.resolve()
 try:
  if a.stage=='hv':hv()
  else:av(a.stage=='b')
  save(DEST/'status.json',dict(stage=a.stage+'_complete',**stamp()))
 except Exception as e:
  save(DEST/'status.json',dict(stage='error',error=repr(e),**stamp()));raise
 print(a.stage,'complete')
if __name__=='__main__':main()

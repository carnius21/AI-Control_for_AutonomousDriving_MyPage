"""One AV per route on frozen HV inputs; no training or action overrides."""
import concurrent.futures as cf
import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as E
from utils import resume_validation as r
from env.navigation_observation import RouteNavigation
import env.ic_experiment as ic

b=r.b
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/av_hv_release_20261113'
SOURCES={'reference':ROOT/'scenarios/hv_high15000_entryprep',
         'high_exit40':ROOT/'results/hv_observed_bounds_20261113/inputs/high_exit40'}

def one(spec):
    mode,route=spec;b.torch.set_num_threads(1)
    dest=OUT/'runs'/f'{mode}-{route}';dest.mkdir(parents=True,exist_ok=True)
    if (dest/'complete.json').exists():return json.loads((dest/'complete.json').read_text())
    inp=OUT/'inputs'/mode
    net=E.parse(inp/'network.net.xml');edges={e.get('id'):e for e in net.findall('edge') if not e.get('function')}
    paths={e.get('id'):e.get('edges').split() for e in E.parse(inp/'highway.rou.xml').findall('route') if e.get('id').startswith('route_')}
    connections=[(c.get('from'),c.get('to'),int(c.get('fromLane')),int(c.get('toLane'))) for c in net.findall('connection') if c.get('from') in edges and c.get('to') in edges]
    lengths={k:max(float(l.get('length')) for l in e.findall('lane')) for k,e in edges.items()}
    internal={l.get('id'):float(l.get('length')) for e in net.findall('edge') if e.get('function')=='internal' for l in e.findall('lane')}
    links={}
    for c in net.findall('connection'):
        key=(c.get('from'),c.get('to'));links[key]=max(links.get(key,0),internal.get(c.get('via'),0))
    nav=RouteNavigation({k:len(e.findall('lane')) for k,e in edges.items()},connections,lengths,horizon=b.NAV.horizon,link_lengths=links)
    road=dict(b.ROAD_NEW,routes=paths,edges=[(k,e.get('from'),e.get('to'),len(e.findall('lane'))) for k,e in edges.items()],connections=connections,
        solid_lane_edges=[k for k,e in edges.items() if any(l.get('changeLeft') or l.get('changeRight') for l in e.findall('lane'))])
    ic.RAMPS={k for k,e in edges.items() if e.get('type','').endswith('_link')};ic.ZIP=()
    modeldir=r.sources('baseline',22);model=modeldir/'policy-600064.pt';m=json.loads((modeldir/'manifest.json').read_text())
    agent=b.PPO(obs_dim=47,act_dim=2,**m['hp']);agent.load(str(model))
    sim=dict(m['simulation'],max_steps=54000,warmup_steps=4500)
    env=r.c.ClarityEnv(str(inp/'run.sumocfg'),road,dict(m['ego'],depart_lane='best',depart_speed='max'),sim,b.OBSERVATION,m['action'],m['reward'],dict(b.TRAFFIC,prefill={'enabled':False}),(),22,navigation=nav,clarity='baseline')
    assert env.step_length==.2
    env.insert_wait_steps=54000
    row=dict(mode=mode,route=route,simulation_seed=9101,training_seed=22,model=str(model),model_sha=b.digest(model),map_sha=b.digest(inp/'network.net.xml'),forced_correction=False)
    trace=b.TimeoutTrace();samples=[];teleports=0;collision_ids=[]
    try:
        try:obs,_=env.reset(seed=9101,options={'route':route})
        except RuntimeError as exc:
            if '삽입 실패' not in str(exc):raise
            row.update(outcome='insertion_failure',error=str(exc));r.save(dest/'complete.json',row);return row
        row['actual_depart_time']=b.traci.simulation.getTime();row['insertion_delay']=max(0,row['actual_depart_time']-900.2)
        while True:
            v=b.traci.vehicle;lead=v.getLeader(env.ego_id,200)
            action=agent.predict(obs,deterministic=True)
            sample=dict(t=env.step_count*.2,lane=v.getLaneID(env.ego_id),speed=v.getSpeed(env.ego_id),position=v.getLanePosition(env.ego_id),leader=lead,leader_speed=v.getSpeed(lead[0]) if lead else None,action=action.tolist(),nav=env.navigation_context())
            if env.step_count%5==0:trace.sample(env);samples.append(sample)
            obs,_,done,cut,info=env.step(action)
            teleports+=b.traci.simulation.getStartingTeleportNumber()
            collision_ids.extend(b.traci.simulation.getCollidingVehiclesIDList())
            if env.step_count%500==0:r.save(dest/'progress.json',dict(pid=os.getpid(),seconds=env.step_count*.2))
            if done or cut:break
        assert env.route_override_count==0
        row.update(outcome='collision' if info['collided'] else 'arrival' if info['arrived'] else 'timeout' if cut else 'other',
            seconds=env.step_count*.2,teleports=teleports,collision_ids=collision_ids,last=sample,diagnostic=trace.result(),route_overrides=env.route_override_count)
        r.save(dest/'trace.json',samples);r.save(dest/'complete.json',row);return row
    finally:env.close()

def main():
    OUT.mkdir(parents=True,exist_ok=True);lock=OUT/'active.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        for mode,src in SOURCES.items():
            d=OUT/'inputs'/mode;d.mkdir(parents=True,exist_ok=True)
            for name in ('network.net.xml','highway.rou.xml','run.sumocfg'):shutil.copy2(src/name,d/name)
        r.save(OUT/'manifest.json',dict(commit=b.COMMIT,warmup_seconds=900,drive_limit_seconds=10800,insert_limit_seconds=10800,
            sources={m:{n:b.digest(p/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')} for m,p in SOURCES.items()},policy='navigation-only baseline-22 policy-600064.pt',no_training=True))
        r.save(OUT/'status.json',dict(stage='running',pid=os.getpid(),cases=32))
        with cf.ProcessPoolExecutor(max_workers=6) as pool:
            for x in pool.map(one,[(m,f'route_{i:02d}') for m in SOURCES for i in range(1,17)]):print(x['mode'],x['route'],x['outcome'],flush=True)
        r.save(OUT/'status.json',dict(stage='complete',cases=32))
    except Exception as exc:r.save(OUT/'status.json',dict(stage='error',error=repr(exc)));raise
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':main()

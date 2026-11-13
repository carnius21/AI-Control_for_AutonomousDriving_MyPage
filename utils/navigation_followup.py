"""Bounded, gated follow-up on the frozen corrected map. No route action override."""
import argparse, collections, copy, json, os, shutil, subprocess, time
from pathlib import Path
import xml.etree.ElementTree as ET
from utils import train_navigation_route04 as base
from env.road_builder import _ic_write_routes

ROOT=base.ROOT
OUT=ROOT/'results/navigation_followup_v2'
DOC=ROOT/'docs/ic-next-stages-results.md'
SEEDS=(11,22,33)
ROUTES=list(base.MAN['routes'])
COUNTS={e:len(x.findall('lane')) for e,x in base.EDGES.items()}


def demand(routes, counts, per_lane):
    entries=collections.Counter(path[0] for path in routes.values())
    return {r:per_lane*counts[p[0]]/entries[p[0]] for r,p in routes.items()}


def gate(rows, routes):
    for route in routes:
        group=[r for r in rows if r['route']==route]
        if len(group)<20:return False
        if sum(r['arrival'] for r in group)/len(group)<.95:return False
        if sum(r['collision'] for r in group)/len(group)>=.05:return False
        if any(r.get('teleports',0) or r.get('insertion_failure',False) for r in group):return False
    return True


def verify_hashes(hashes):
    for name, expected in hashes.items():
        if not Path(name).exists() or base.digest(Path(name))!=expected:
            raise RuntimeError('Cached input changed: '+name)


def cached_run(directory):
    meta=read(directory/'manifest.json')
    verify_hashes({str(ROOT/p):h for p,h in meta['sources'].items()})
    if meta.get('source'):verify_hashes({meta['source']:meta['source_sha']})
    marker=read(directory/'complete.json')
    if 'model_sha' in marker:verify_hashes({str(directory/'model.pt'):marker['model_sha']})


def check_disk():
    if shutil.disk_usage(OUT).free<20*1024**3:raise RuntimeError('Less than 20GiB free; stopped before next stage')


def read(path):return json.loads(path.read_text(encoding='utf8'))
def save(path,obj):base.save(path,obj)

def stamp():
    data=base.stamp();data['simulation_seed_policy']='training: seeded per-episode generator; HV:1001..1003; evaluation:40001..40020'
    return data


def state(stage, **kwargs):
    save(OUT/'status.json',dict(stage=stage,pid=os.getpid(),updated=time.time(),**stamp(),**kwargs))


def publish(label):
    lines=['# 수정 맵 후속 실험 결과','',f'현재 단계: **{label}**','',
           '합성 수요이며 실측 교통량이 아니다. 강제 경로 보정은 사용하지 않는다. [실험 조건·통과 기준](ic-next-stages-plan.md).',
           '', '## HV 단독 검증','', '| 수요/seed | 예정/삽입/도착 | 충돌 차량 누계 | 텔레포트 | 통과 |','|---|---|---:|---:|---|']
    for p in sorted((OUT/'hv').glob('*.json')):
        r=read(p);lines.append(f"| {r['load']}/{r['seed']} | {r['expected']}/{r['inserted']}/{r['arrived']} | {r['collisions']} | {r['teleports']} | {r['pass']} |")
    lines+=['','## AV 평가 (완료된 평가만)','', '| 실행 | 경로 | 완주/횟수 | 충돌 | 시간초과 | 원인 분류 |','|---|---|---|---:|---:|---|']
    for p in sorted(OUT.glob('**/evaluation.json')):
        rows=read(p)
        for route in sorted({r['route'] for r in rows}):
            group=[r for r in rows if r['route']==route]
            causes=dict(collections.Counter(r['failure'] for r in group if not r['arrival']))
            lines.append(f"| {p.parent.relative_to(OUT)} | {route} | {sum(r['arrival'] for r in group)}/{len(group)} | {sum(r['collision'] for r in group)} | {sum(r.get('timeout',False) for r in group)} | {causes} |")
    lines+=['','## 보상 진단 (완료된 평가)','','| 실행 | 준비 성공/판정 | 과속/램프 스텝 | 보상 성분 합 |','|---|---:|---:|---|']
    for p in sorted((OUT/'runs').glob('*/evaluation.json')):
        rows=read(p);m=collections.Counter();rw=collections.Counter()
        for row in rows:m.update(row.get('metrics',{}));rw.update(row.get('reward_sums',{}))
        lines.append(f"| {p.parent.name} | {m['route_ready']}/{m['route_checks']} | {m['overspeed_steps']}/{m['ramp_steps']} | {dict(rw)} |")
    lines+=['','각 run의 manifest에 실행 커밋·seed·맵/코드/모델 해시·설정·선행 모델을 보존한다. 모델과 사례 추적은 로컬 results/navigation_followup_v2에만 저장한다.',
            '', '현재 맵의 우선권을 유지했다. 옛 사노 지퍼 이벤트는 적용되지 않으므로 ZIP 보상은 검증 대기다. 평가 미달 이후 단계는 자동 차단한다.']
    DOC.write_text('\n'.join(lines)+'\n',encoding='utf8')
    rel=str(DOC.relative_to(ROOT))
    subprocess.run(['git','add',rel],cwd=ROOT,check=True)
    if subprocess.check_output(['git','diff','--cached','--name-only','--',rel],cwd=ROOT).strip():
        subprocess.run(['git','commit','--only','-m','Record navigation follow-up: '+label,'--',rel],cwd=ROOT,check=True)
    subprocess.run(['git','push','origin','main'],cwd=ROOT,check=True)


def prepare(load, hv=False):
    directory=OUT/'traffic_v2'/(load+('-hv' if hv else ''))
    cfg=directory/'run.sumocfg'
    if cfg.exists():
        meta=read(directory/'manifest.json');verify_hashes(meta['files'])
        if meta['generator_sha']!=base.digest(Path(__file__)):raise RuntimeError('Cached traffic generator changed')
        return cfg
    directory.mkdir(parents=True,exist_ok=True)
    rates=demand(base.MAN['routes'],COUNTS,{'none':0,'low':300,'base':600}[load])
    traffic=copy.deepcopy(base.TRAFFIC)
    traffic.update(flows={r:(v,'0.5,0.5,0.5') for r,v in rates.items()},vehs_per_hour=sum(rates.values()),flow_end=900 if hv else 3600,demo_vehicle=False)
    road=dict(base.ROAD_NEW,ego_route=ROUTES[0])
    _ic_write_routes(directory,road,base.EGO,traffic)
    shutil.copy2(base.MAP/'network.net.xml',directory/'network.net.xml')
    tree=ET.Element('configuration');inp=ET.SubElement(tree,'input')
    ET.SubElement(inp,'net-file',value='network.net.xml');ET.SubElement(inp,'route-files',value='highway.rou.xml')
    processing=ET.SubElement(tree,'processing');ET.SubElement(processing,'time-to-teleport',value='-1')
    ET.ElementTree(tree).write(cfg,encoding='utf8',xml_declaration=True)
    save(directory/'manifest.json',dict(rates=rates,total_vph=sum(rates.values()),traffic=traffic,network_sha256=base.digest(directory/'network.net.xml'),zipper_event_supported=False,generator_sha=base.digest(Path(__file__)),files={str(directory/n):base.digest(directory/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')},**{'git':base.COMMIT}))
    return cfg


def environment(mode,seed,load='none',routes=None,variants=()):
    cfg=prepare(load)
    road=dict(base.ROAD_NEW,routes={r:base.MAN['routes'][r] for r in (routes or ROUTES)})
    sim=dict(base.SIMULATION,warmup_steps=300 if load!='none' else base.SIMULATION['warmup_steps'])
    return base.NavigationEnv(str(cfg),road,dict(base.EGO,depart_lane='best',depart_speed='max'),sim,base.OBSERVATION,base.ACTION,base.REWARD,
        dict(base.TRAFFIC,prefill={'enabled':False}),variants,seed,observation_mode=mode,navigation=base.NAV)


def hv_case(load,seed):
    target=OUT/'hv'/f'{load}-{seed}.json'
    cfg=prepare(load,True)
    if target.exists():
        old=read(target);verify_hashes(old['inputs']);return old['pass']
    state('hv',load=load,seed=seed)
    traci=base.traci
    traci.start([base.checkBinary('sumo'),'-c',str(cfg),'--step-length','.2','--seed',str(seed),'--no-step-log','true','--collision.action','remove'])
    inserted=arrived=collisions=teleports=0;types=collections.Counter();perroute=collections.defaultdict(lambda:dict(inserted=0,arrived=0));vehicle_routes={};samples=[]
    try:
        for i in range(9000):
            traci.simulationStep()
            for v in traci.simulation.getDepartedIDList():
                inserted+=1;types[traci.vehicle.getTypeID(v)]+=1
                route=traci.vehicle.getRouteID(v);vehicle_routes[v]=route;perroute[route]['inserted']+=1
            for v in traci.simulation.getArrivedIDList():
                arrived+=1;perroute[vehicle_routes[v]]['arrived']+=1
            collisions+=traci.simulation.getCollidingVehiclesNumber();teleports+=traci.simulation.getStartingTeleportNumber()
            if i%50==0:
                ids=traci.vehicle.getIDList()
                samples.append(dict(t=(i+1)*.2,vehicles=len(ids),stopped=sum(traci.vehicle.getSpeed(v)<.5 for v in ids)))
            if (i+1)*.2>=900 and traci.simulation.getMinExpectedNumber()==0:break
        leftovers=[dict(id=v,route=traci.vehicle.getRouteID(v),lane=traci.vehicle.getLaneID(v),position=traci.vehicle.getLanePosition(v),speed=traci.vehicle.getSpeed(v),waiting=traci.vehicle.getWaitingTime(v)) for v in traci.vehicle.getIDList()]
        flowroot=ET.parse(cfg.parent/'highway.rou.xml').getroot()
        import math
        expected=sum(math.ceil(float(f.get('vehsPerHour'))/4-1e-9) for f in flowroot.findall('flow'))
        passed=inserted>=expected*.95 and arrived>=inserted*.95 and collisions==teleports==0 and all(r['arrived']>=r['inserted']*.95 for r in perroute.values())
        save(target,dict(load=load,seed=seed,expected=expected,inserted=inserted,arrived=arrived,collisions=collisions,teleports=teleports,inputs={str(cfg.parent/n):base.digest(cfg.parent/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')}|{str(Path(__file__).resolve()):base.digest(Path(__file__))},types=dict(types),routes=dict(perroute),samples=samples,leftovers=leftovers,**{'pass':passed},**stamp()))
        return passed
    finally:traci.close()


def evaluate(agent,mode,seed,load,routes,count=20,variants=()):
    rows=[];env=environment(mode,seed,load,routes,tuple(variants)+('MEASURE_ROUTE',))
    try:
        for route in routes:
            for i in range(count):
                simseed=40001+i
                row=dict(route=route,seed=simseed,training_seed=seed,load=load,arrival=False,collision=False,timeout=False,teleports=0,insertion_failure=False)
                try:obs,_=env.reset(seed=simseed,options={'route':route})
                except RuntimeError as exc:
                    if '삽입 실패' not in str(exc):raise
                    rows.append(dict(row,insertion_failure=True,failure='insertion_failure',error=str(exc)));continue
                trace=base.TimeoutTrace();teleports=0;requests=rejected=0
                metrics=dict(route_checks=0,route_ready=0,ramp_steps=0,overspeed_steps=0,overspeed_sum_mps=0.,return_sum=0.)
                reward_sums=collections.Counter()
                while True:
                    if env.step_count%5==0:trace.sample(env)
                    obs,reward,done,cut,info=env.step(agent.predict(obs,deterministic=True))
                    event=info['ic_event'];metrics['return_sum']+=float(reward)
                    if event.get('route_lane_ready') is not None:
                        metrics['route_checks']+=1;metrics['route_ready']+=int(event['route_lane_ready'])
                    metrics['ramp_steps']+=int(event['ramp']);metrics['overspeed_steps']+=int(event['ramp_excess_mps']>0)
                    metrics['overspeed_sum_mps']+=float(event['ramp_excess_mps'])
                    reward_sums.update(event.get('reward_components',{}))
                    teleports+=base.traci.simulation.getStartingTeleportNumber()
                    requested=bool(info.get('lane_change',0));requests+=requested;rejected+=requested and not info.get('lane_change_applied',False)
                    if done or cut:break
                diagnostic=trace.result();arrival=bool(info['arrived']) and not teleports
                failure='none' if arrival else 'collision' if info['collided'] else 'teleport' if teleports else 'wrong_exit' if info['ic_event']['wrong_exit'] else diagnostic['category']
                rows.append(dict(row,arrival=arrival,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,failure=failure,diagnostic=diagnostic,requests=requests,rejected=rejected,route_overrides=env.route_override_count,seconds=env.step_count*env.step_length,metrics=metrics,reward_sums=dict(reward_sums)))
    finally:env.close()
    return rows


def manifest(directory,**kwargs):
    check_disk();directory.mkdir(parents=True)
    sources=['utils/navigation_followup.py','utils/train_navigation_route04.py','env/navigation_observation.py','env/ic_experiment.py','env/sumo_env.py','env/road_builder.py','algorithms/ppo.py','utils/networks.py','env/mdp_config.py','env/road_config.py','train.py','utils/ic_timeout_trace.py','maps/toegyewon_only/network.net.xml','docs/experiments/ic-navigation-plan-v1.json']
    hashes={}
    for src in sources:
        dst=directory/'snapshot'/src;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/src,dst);hashes[src]=base.digest(dst)
    save(directory/'manifest.json',dict(**stamp(),sources=hashes,action_overrides=False,**kwargs))


def frozen(loads):
    for route in ('route_04','route_14'):
        for mode in ('N0','N1','N2'):
            for seed in SEEDS:
                source=ROOT/f'results/navigation_{route.replace("_", "")}_v1/runs/{mode}-{seed}-200000'
                for load in loads:
                    d=OUT/'frozen'/f'{route}-{mode}-{seed}-{load}'
                    if (d/'complete.json').exists():
                        cached_run(d);continue
                    if d.exists():raise RuntimeError(f'Partial case preserved: {d}')
                    state('frozen',case=d.name)
                    manifest(d,source=str(source/'model.pt'),source_sha=base.digest(source/'model.pt'))
                    agent=base.PPO(obs_dim=37,act_dim=2,**read(source/'manifest.json')['hp']);agent.load(str(source/'model.pt'))
                    rows=evaluate(agent,mode,seed,load,[route],5)
                    save(d/'evaluation.json',rows);save(d/'complete.json',dict(done=True))
                    publish('frozen '+d.name)


def train(stage,mode,seed,load,source=None,variants=(),budget=800000,smoke=False):
    d=OUT/('smoke' if smoke else 'runs')/f'{stage}-{mode}-{seed}'
    if (d/'complete.json').exists():
        cached_run(d);return d,read(d/'evaluation.json')
    if d.exists():raise RuntimeError(f'Partial training preserved: {d}')
    state('training',case=d.name,budget=budget)
    hp=dict(base.PLAN['hparams'],seed=seed);env=environment(mode,seed,load,variants=variants)
    manifest(d,hp=hp,mode=mode,seed=seed,load=load,budget=budget,routes=ROUTES,variants=list(variants),source=str(source) if source else None,source_sha=base.digest(source) if source else None,simulation=dict(env.sim) if hasattr(env,'sim') else {'dt':env.step_length,'warmup_steps':env.warmup_steps},traffic_manifest=read(prepare(load).parent/'manifest.json'))
    agent=base.PPO(obs_dim=37,act_dim=2,buffer=base.RolloutBuffer(),**hp)
    if source:agent.load(str(source))
    agent.save(str(d/'initial.pt'));logger=base.Log(d,agent,budget,env)
    try:
        agent.learn(env,budget,logger=logger,eval_interval=0,exact_budget=True)
        assert agent.num_timesteps==budget and env.route_override_count==0
        agent.save(str(d/'model.pt'))
    finally:env.close();logger.close()
    rows=[] if smoke else evaluate(agent,mode,seed,load,ROUTES,variants=variants)
    save(d/'evaluation.json',rows);save(d/'complete.json',dict(steps=budget,pass_gate=gate(rows,ROUTES),model_sha=base.digest(d/'model.pt')))
    if not smoke:publish('evaluated '+d.name)
    return d,rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);lock=OUT/'active.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    base.torch.set_num_threads(1)
    try:
        if base.digest(base.MAP/'network.net.xml')!=base.PLAN['map_sha256']:raise RuntimeError('Frozen map changed')
        check_disk()
        if args.smoke:
            for mode in ('N0','N1'):
                train('smoke-v2',mode,11,'low',budget=2048,smoke=True)
            state('smoke_complete');return
        passed={}
        for load in ('low','base'):
            passed[load]=[]
            for seed in (1001,1002,1003):
                check_disk();passed[load].append(hv_case(load,seed));publish('HV '+load+' '+str(seed))
        if not all(passed['low']):
            state('blocked_hv',reason='HV passage gate failed; dependent AV/training not started');publish('blocked: HV gate');return
        eligible=[load for load,values in passed.items() if all(values)]
        save(OUT/'eligible-loads.json',dict(eligible=eligible,blocked=[load for load in passed if load not in eligible]))
        frozen(eligible)
        sources={};success=True
        for mode in ('N0','N1'):
            for seed in SEEDS:
                d,rows=train('shared',mode,seed,'none')
                if mode=='N1':sources[seed]=d/'model.pt';success=success and gate(rows,ROUTES)
        if not success:
            state('blocked_shared',reason='N1 failed per-route gate');publish('blocked: shared policy gate');return
        for load in ('low','base'):
            if load not in eligible:
                state('blocked_base_demand',reason='Low-demand work complete; base HV insertion gate failed; no base training or reward tests')
                publish('low-demand complete; base demand blocked');return
            success=True
            for seed in SEEDS:
                d,rows=train('traffic-'+load,'N1',seed,load,sources[seed]);sources[seed]=d/'model.pt';success=success and gate(rows,ROUTES)
            if not success:
                state('blocked_traffic',load=load,reason='Per-route gate failed');publish('blocked: '+load+' traffic gate');return
        for variants in ((),('ROUTE100',),('RAMP',)):
            label='control' if not variants else variants[0]
            for seed in SEEDS:train('reward-'+label,'N1',seed,'base',sources[seed],variants)
        state('awaiting_zipper_validation',reason='Independent route/ramp experiments complete; ZIP event requires current-map validation before combinations/final collection')
        publish('independent rewards complete; ZIP validation pending')
    except Exception as exc:
        state('error',error=repr(exc))
        try:publish('error; preserved for diagnosis')
        except Exception:pass
        raise
    finally:lock.unlink()

if __name__=='__main__':main()

"""Sequential, bounded observation-only comparison with provenance and reports."""
import argparse
import os
import shutil
import subprocess
import time
from pathlib import Path
from utils import navigation_followup as f
from env.navigation_clarity import ClarityEnv

OUT = f.ROOT/'results/navigation_clarity_v1'
DOC = f.ROOT/'docs/experiments/ic-navigation-clarity.md'
MODES = ('baseline','validity','lookahead')
SOURCES = ['env/navigation_clarity.py','env/navigation_observation.py','env/ic_experiment.py','env/sumo_env.py','env/mdp_config.py','env/road_config.py','algorithms/ppo.py','utils/networks.py','utils/train_navigation_clarity.py','utils/navigation_followup.py','utils/train_navigation_route04.py','utils/check_toegyewon_only.py','train.py','maps/toegyewon_only/network.net.xml']


def environment(mode, seed, lane='best', speed='max'):
    b = f.base
    return ClarityEnv(str(f.prepare('none')),dict(b.ROAD_NEW,routes=b.MAN['routes']),
        dict(b.EGO,depart_lane=lane,depart_speed=speed), b.SIMULATION,b.OBSERVATION,b.ACTION,b.REWARD,
        dict(b.TRAFFIC,prefill={'enabled':False}),(),seed,navigation=b.NAV,clarity=mode)


def evaluate(agent, mode, seed):
    rows=[]
    for route in f.ROUTES:
        last=f.COUNTS[f.base.MAN['routes'][route][0]]-1
        starts=list(dict.fromkeys([('best','max'),('0','5'),('0','15'),(str(last),'15')]))
        for n,(lane,speed) in enumerate(starts):
            env=environment(mode,seed,lane,speed)
            row=dict(route=route,lane=lane,speed=speed,simulation_seed=50001+n,arrival=False,collision=False,insertion_failure=False)
            try:
                try:obs,_=env.reset(seed=50001+n,options={'route':route})
                except RuntimeError as exc:
                    if '삽입 실패' not in str(exc):raise
                    rows.append(dict(row,insertion_failure=True,error=str(exc)));continue
                trace=f.base.TimeoutTrace();teleports=0
                while True:
                    if env.step_count%5==0:trace.sample(env)
                    obs,_,done,cut,info=env.step(agent.predict(obs,deterministic=True))
                    teleports+=f.base.traci.simulation.getStartingTeleportNumber()
                    if done or cut:break
                assert env.route_override_count==0
                rows.append(dict(row,arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,seconds=env.step_count*env.step_length,route_overrides=0,diagnostic=trace.result()))
            finally:env.close()
    return rows


def publish():
    # The legacy runner has no report lock. During migration, let it finish first.
    while (OUT/'legacy-publisher.active').exists():
        time.sleep(1)
    lock=OUT/'report.lock'
    while True:
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd);break
        except FileExistsError:time.sleep(1)
    try:
        _publish()
    finally:lock.unlink()


def _publish():
    lines=['## 비교 실행 결과','','동일 seed의 세 조건은 같은 초기 가중치에서 시작한다. 삽입 불가는 별도 표기하며 성공으로 처리하지 않는다.','','| 조건 | 학습 seed | 완주/전체 | 충돌 | 시간초과 | 삽입 불가 | 실행 경로 |','|---|---:|---:|---:|---:|---:|---|']
    details=[]
    for d in sorted((OUT/'runs').glob('*')):
        if not (d/'complete.json').exists():continue
        meta=f.read(d/'manifest.json');rows=f.read(d/'evaluation.json')
        lines.append(f"| {meta['condition']} | {meta['seed']} | {sum(r['arrival'] for r in rows)}/{len(rows)} | {sum(r['collision'] for r in rows)} | {sum(r.get('timeout',False) for r in rows)} | {sum(r['insertion_failure'] for r in rows)} | `{d.relative_to(f.ROOT)}` |")
        for route in f.ROUTES:
            cases=[r for r in rows if r['route']==route]
            details.append(f"- {d.name} / {route}: {sum(r['arrival'] for r in cases)}/{len(cases)} 완주. 실행 코드 `{meta['commit']}`.")
    lines += ['','### 경로별 결과',''] + details
    prefix=DOC.read_text(encoding='utf8').split('## 비교 실행 결과')[0]
    DOC.write_text(prefix+'\n'+'\n'.join(lines)+'\n',encoding='utf8')
    rel=str(DOC.relative_to(f.ROOT))
    subprocess.run(['git','add','--',rel],cwd=f.ROOT,check=True)
    subprocess.run(['git','commit','--only','-m','Record completed navigation clarity comparison','--',rel],cwd=f.ROOT,check=True)
    subprocess.run(['git','push','origin','main'],cwd=f.ROOT,check=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true');parser.add_argument('--seed',type=int,choices=(11,22,33));args=parser.parse_args()
    f.base.torch.set_num_threads(1);OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/(f'active-{args.seed}.lock' if args.seed else 'active.lock');fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    def status(stage,**kw):f.save(OUT/(f'status-{args.seed}.json' if args.seed else 'status.json'),dict(stage=stage,pid=os.getpid(),updated=time.time(),**kw))
    hashes={s:f.base.digest(f.ROOT/s) for s in SOURCES}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=f.ROOT,text=True).strip()
    try:
        assert hashes['maps/toegyewon_only/network.net.xml']==f.base.PLAN['map_sha256']
        for seed in ((args.seed,) if args.seed else (11,) if args.smoke else (11,22,33)):
            initial_hash=None
            for mode in MODES:
                f.check_disk()
                assert all(f.base.digest(f.ROOT/s)==h for s,h in hashes.items()), 'Source changed during campaign'
                budget=2048 if args.smoke else 800000
                d=OUT/('smoke' if args.smoke else 'runs')/f'{mode}-{seed}'
                if args.seed and (d/'complete.json').exists():
                    previous=f.read(d/'manifest.json');complete=f.read(d/'complete.json')
                    assert complete['steps']==budget and previous['hp']==dict(f.base.PLAN['hparams'],seed=seed)
                    assert f.base.digest(d/'model.pt')==complete['model_sha']
                    # Only orchestration changed during the sequential-to-parallel handoff.
                    assert all(f.base.digest(f.ROOT/s)==h for s,h in previous['hashes'].items() if s!='utils/train_navigation_clarity.py')
                    if initial_hash is None:initial_hash=previous['initial_sha']
                    assert initial_hash==previous['initial_sha']
                    continue
                if d.exists():raise RuntimeError('Existing run preserved: '+str(d))
                d.mkdir(parents=True)
                hp=dict(f.base.PLAN['hparams'],seed=seed)
                env=environment(mode,seed)
                agent=f.base.PPO(obs_dim=47,act_dim=2,buffer=f.base.RolloutBuffer(),**hp)
                agent.save(str(d/'initial.pt'))
                h=f.base.digest(d/'initial.pt')
                if initial_hash is None:initial_hash=h
                assert initial_hash==h, 'Paired initial weights differ'
                for src in SOURCES:
                    dst=d/'snapshot'/src;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f.ROOT/src,dst)
                f.save(d/'manifest.json',dict(condition=mode,seed=seed,budget=budget,hp=hp,commit=commit,hashes=hashes,initial_sha=h,routes=f.ROUTES,action_overrides=False,observation_dim=47,simulation=f.base.SIMULATION,action=f.base.ACTION,reward=f.base.REWARD,ego=dict(f.base.EGO,depart_lane='best',depart_speed='max')))
                logger=f.base.Log(d,agent,budget,env);status('smoke' if args.smoke else 'training',condition=mode,seed=seed,target=budget)
                try:
                    agent.learn(env,budget,logger=logger,eval_interval=0,exact_budget=True)
                    assert agent.num_timesteps==budget and env.route_override_count==0
                    agent.save(str(d/'model.pt'))
                finally:env.close();logger.close()
                status('evaluation',condition=mode,seed=seed)
                rows=[] if args.smoke else evaluate(agent,mode,seed)
                f.save(d/'evaluation.json',rows)
                f.save(d/'complete.json',dict(steps=budget,model_sha=f.base.digest(d/'model.pt'),action_overrides=0))
                if not args.smoke:publish()
        status('smoke_complete' if args.smoke else 'complete')
    except Exception as exc:
        status('error',error=repr(exc));raise
    finally:lock.unlink()


if __name__=='__main__':main()

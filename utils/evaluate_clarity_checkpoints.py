"""Parallel checkpoint audit. Same 62 starts; no training or action overrides."""
import concurrent.futures
import json
import os
import subprocess
import time
from pathlib import Path
from utils import train_navigation_clarity as c

f=c.f
OUT=f.ROOT/'results/navigation_clarity_checkpoints_v1'
COARSE=(200704,401408,600064)


def key(row):
    return (row['route'],str(row['lane']),str(row['speed']))


def evaluate_cases(agent, mode, seed, cases):
    rows=[]
    for case in cases:
        row={k:case[k] for k in ('route','lane','speed','simulation_seed')}
        env=c.environment(mode,seed,case['lane'],case['speed'])
        try:
            try:obs,_=env.reset(seed=case['simulation_seed'],options={'route':case['route']})
            except RuntimeError as exc:
                if '삽입 실패' not in str(exc):raise
                rows.append(dict(row,arrival=False,collision=False,timeout=False,insertion_failure=True,error=str(exc)));continue
            teleports=0
            while True:
                v=f.base.traci.vehicle
                final=dict(edge=v.getRoadID(env.ego_id),lane=v.getLaneIndex(env.ego_id),speed=v.getSpeed(env.ego_id),nav=env.navigation_context())
                action=agent.predict(obs,deterministic=True)
                obs,_,done,cut,info=env.step(action)
                teleports+=f.base.traci.simulation.getStartingTeleportNumber()
                if done or cut:break
            assert env.route_override_count==0
            rows.append(dict(row,arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),insertion_failure=False,teleports=teleports,seconds=env.step_count*env.step_length,final=final,final_action=action.tolist(),route_overrides=0))
        finally:env.close()
    return rows


def audit(name):
    f.base.torch.set_num_threads(1)
    source=c.OUT/'runs'/name;meta=f.read(source/'manifest.json');done=f.read(source/'complete.json')
    assert f.base.digest(source/'model.pt')==done['model_sha']
    for src,h in meta['hashes'].items():
        if src!='utils/train_navigation_clarity.py':assert f.base.digest(f.ROOT/src)==h,src
    directory=OUT/name;directory.mkdir(parents=True,exist_ok=True)
    def status(stage,**kw):f.save(directory/'status.json',dict(stage=stage,pid=os.getpid(),updated=time.time(),**kw))
    final=f.read(source/'evaluation.json');final_fail={key(r):r for r in final if not r['arrival']}
    histories={k:[] for k in final_fail}
    checkpoints=sorted((int(p.stem.split('-')[1]),p) for p in source.glob('policy-*.pt'))
    hashes={str(step):f.base.digest(p) for step,p in checkpoints}
    f.save(directory/'manifest.json',dict(source=str(source),source_manifest=meta,checkpoint_hashes=hashes,coarse=COARSE,script_sha=f.base.digest(Path(__file__)),evaluation='exact original physical starts and simulation seeds',adaptive='scan all remaining saved checkpoints for final failures until a prior success is found'))
    summaries=[]
    try:
        for step in COARSE:
            status('coarse',step=step)
            target=directory/f'{step}.json'
            if target.exists():rows=f.read(target)
            else:
                agent=f.base.PPO(obs_dim=47,act_dim=2,**meta['hp']);agent.load(str(source/f'policy-{step}.pt'))
                rows=evaluate_cases(agent,meta['condition'],meta['seed'],final);f.save(target,rows)
            summaries.append(dict(step=step,arrivals=sum(r['arrival'] for r in rows),cases=len(rows)))
            for r in rows:
                if key(r) in histories and r['arrival']:histories[key(r)].append(step)
        for step,path in checkpoints:
            unresolved=[final_fail[k] for k,successes in histories.items() if not successes]
            if not unresolved:break
            if step in COARSE or step>=800000:continue
            status('adaptive',step=step,unresolved=len(unresolved))
            target=directory/f'adaptive-{step}.json'
            if target.exists():rows=f.read(target)
            else:
                agent=f.base.PPO(obs_dim=47,act_dim=2,**meta['hp']);agent.load(str(path))
                rows=evaluate_cases(agent,meta['condition'],meta['seed'],unresolved);f.save(target,rows)
            for r in rows:
                if r['arrival']:histories[key(r)].append(step)
        failures=[dict(route=k[0],lane=k[1],speed=k[2],category='learned_then_lost' if steps else 'never_passed_saved_checkpoints',successful_steps=sorted(steps)) for k,steps in histories.items()]
        result=dict(name=name,mode=meta['condition'],seed=meta['seed'],coarse=summaries,final_arrivals=sum(r['arrival'] for r in final),cases=len(final),regressions=sum(bool(x) for x in histories.values()),never_observed=sum(not x for x in histories.values()),failures=failures)
        f.save(directory/'complete.json',result);status('complete');return result
    except Exception as exc:status('error',error=repr(exc));raise


def report(results):
    doc=c.DOC;marker='## 중간 저장 모델 평가'
    lines=[marker,'','같은 62개 출발 조건으로 20만·40만·60만 단계 저장 모델을 전수 평가했다. 마지막에 실패한 사례는 이전 성공이 발견될 때까지 나머지 약2만 단계 간격 저장 모델도 확인했다. 이전 성공이 없는 경우 모든 이전 저장 모델에서 실패했음을 뜻하며, 저장 사이의 모든 순간까지 증명하지 않는다.','','| 조건 | 초기값 | 20만 | 40만 | 60만 | 80만 | 성공 후 실패 사례 | 저장 모델 전체에서 성공 미관측 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in sorted(results,key=lambda r:(r['mode'],r['seed'])):
        values=[str(x['arrivals'])+'/'+str(x['cases']) for x in r['coarse']]
        lines.append('| '+ ' | '.join([r['mode'],str(r['seed']),*values,f"{r['final_arrivals']}/{r['cases']}",str(r['regressions']),str(r['never_observed'])])+' |')
    lines+=['','이는 같은 평가 사례를 돌이켜 본 진단이다. 최고 체크포인트 선택 후 성능은 별도의 미사용 출발 조건에서 검증해야 한다. 원본 기록: `results/navigation_clarity_checkpoints_v1/`. 강제 행동 보정 및 재학습 없음.']
    doc.write_text(doc.read_text(encoding='utf8').split(marker)[0].rstrip()+'\n\n'+'\n'.join(lines)+'\n',encoding='utf8')
    rel=str(doc.relative_to(f.ROOT))
    subprocess.run(['git','add','--',rel],cwd=f.ROOT,check=True)
    subprocess.run(['git','commit','--only','-m','Record parallel intermediate-checkpoint audit','--',rel],cwd=f.ROOT,check=True)
    subprocess.run(['git','push','origin','main'],cwd=f.ROOT,check=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    names=[f'{m}-{s}' for m in c.MODES for s in (11,22,33)]
    results=[]
    def state(stage,**kw):f.save(OUT/'status.json',dict(stage=stage,pid=os.getpid(),updated=time.time(),completed=len(results),total=9,**kw))
    try:
        state('running')
        with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(audit,name):name for name in names}
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result());f.save(OUT/'summary.json',results);state('running',last=futures[future]);report(results)
        state('complete')
    except Exception as exc:state('error',error=repr(exc));raise
    finally:lock.unlink()


if __name__=='__main__':main()

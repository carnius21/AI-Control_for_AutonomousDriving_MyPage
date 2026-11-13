"""Independent lane-learning ablations; six bounded workers, isolated evaluations."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from utils import train_navigation_clarity as c

f=c.f
OUT=f.ROOT/'results/lane_learning_v1'
DOC=f.ROOT/'docs/experiments/ic-lane-learning.md'


def entropy_at(step):
    return .01*max(0.,min(1.,(800000-step)/400000))


class ProgressReward:
    def __init__(self): self.paid=set()
    def award(self,edge,targets,before,after,distance):
        if not targets or distance is None or not 0<=distance<=100: return 0.
        a=min(abs(before-t) for t in targets); b=min(abs(after-t) for t in targets)
        reward=0.
        for level in range(b,a):
            key=(edge,tuple(sorted(targets)),level)
            if key not in self.paid:
                self.paid.add(key); reward+=.1
        return reward


class RewardEnv(c.ClarityEnv):
    def reset(self,*args,**kwargs):
        self.credits=ProgressReward()
        return super().reset(*args,**kwargs)
    def step(self,action):
        v=f.base.traci.vehicle
        edge=v.getRoadID(self.ego_id); lane=v.getLaneIndex(self.ego_id)
        nav=self.navigation_context()
        obs,reward,done,cut,info=super().step(action)
        extra=0.
        if not done and self.ego_id in v.getIDList() and v.getRoadID(self.ego_id)==edge and not edge.startswith(':'):
            extra=self.credits.award(edge,nav['prepare_targets'],lane,v.getLaneIndex(self.ego_id),nav['distance'])
        self.total_progress_reward=getattr(self,'total_progress_reward',0.)+extra
        self.progress_reward_events=getattr(self,'progress_reward_events',0)+int(extra>0)
        info['destination_lane_reward']=extra
        return obs,reward+extra,done,cut,info


class ScheduledPPO(f.base.PPO):
    def update(self,*args,**kwargs):
        self.lane_entropy_coef=entropy_at(self.num_timesteps)
        return super().update(*args,**kwargs)


def environment(mode,seed):
    if mode=='entropy': return c.environment('baseline',seed)
    b=f.base
    return RewardEnv(str(f.prepare('none')),dict(b.ROAD_NEW,routes=b.MAN['routes']),
        dict(b.EGO,depart_lane='best',depart_speed='max'),b.SIMULATION,b.OBSERVATION,b.ACTION,b.REWARD,
        dict(b.TRAFFIC,prefill={'enabled':False}),(),seed,navigation=b.NAV,clarity='baseline')


def evaluate(name,step,reference=False):
    seed=int(name.split('-')[-1])
    source=c.OUT/'runs'/f'baseline-{seed}' if reference else OUT/'runs'/name
    meta=f.read(source/'manifest.json')
    policy=source/(f'policy-{step}.pt' if step<800000 else 'model.pt')
    target=OUT/'evaluations'/('baseline-'+str(seed) if reference else name)/f'{step}.json'
    if target.exists(): return
    f.base.torch.set_num_threads(1)
    agent=f.base.PPO(obs_dim=47,act_dim=2,**meta['hp']); agent.load(str(policy))
    rows=c.evaluate(agent,'baseline',seed)
    f.save(target,dict(step=step,policy_sha=f.base.digest(policy),rows=rows,arrivals=sum(r['arrival'] for r in rows),cases=len(rows)))


class Log(f.base.Log):
    def __init__(self,d,agent,budget,env,name,smoke):
        super().__init__(d,agent,budget,env)
        self.name=name; self.smoke=smoke; self.next_eval=100000
    def log_train(self,step,metrics,verbose=False):
        metrics=dict(metrics,lane_entropy_coef=self.agent.lane_entropy_coef,
            destination_reward_total=getattr(self.env,'total_progress_reward',0.),
            destination_reward_events=getattr(self.env,'progress_reward_events',0))
        super().log_train(step,metrics,verbose)
        if not self.smoke and (step>=self.next_eval or step==self.budget):
            self.agent.save(str(self.directory/f'policy-{step}.pt'))
            if step==self.budget:self.agent.save(str(self.directory/'model.pt'))
            f.save(self.directory/'status.json',dict(stage='evaluating',step=step,pid=os.getpid()))
            command=[sys.executable,'-X','utf8','-m','utils.train_lane_learning','--eval',self.name,'--step',str(step)]
            subprocess.run(command,cwd=f.ROOT,check=True,stdout=subprocess.DEVNULL)
            if self.name.startswith('entropy'):
                subprocess.run(command+['--reference'],cwd=f.ROOT,check=True,stdout=subprocess.DEVNULL)
            self.next_eval+=100000
        f.save(self.directory/'status.json',dict(stage='training',step=step,pid=os.getpid(),updated=time.time()))


def train(spec):
    mode,seed,smoke=spec; name=f'{mode}-{seed}'
    d=OUT/('smoke' if smoke else 'runs')/name
    if (d/'complete.json').exists():return name
    if d.exists():raise RuntimeError('Preserving unfinished run: '+str(d))
    d.mkdir(parents=True);f.base.torch.set_num_threads(1);f.check_disk()
    source=c.OUT/'runs'/f'baseline-{seed}';old=f.read(source/'manifest.json')
    for path,h in old['hashes'].items():
        if path!='utils/train_navigation_clarity.py':assert f.base.digest(f.ROOT/path)==h,path
    hp=old['hp'];env=environment(mode,seed)
    cls=ScheduledPPO if mode in ('entropy','combined') else f.base.PPO
    agent=cls(obs_dim=47,act_dim=2,buffer=f.base.RolloutBuffer(),**hp)
    agent.save(str(d/'initial.pt'))
    assert f.base.digest(d/'initial.pt')==old['initial_sha'],'Initial weights mismatch'
    budget=2048 if smoke else 800000
    manifest=dict(mode=mode,seed=seed,hp=hp,budget=budget,baseline_manifest=old,
        initial_sha=f.base.digest(d/'initial.pt'),action_overrides=False,
        script_sha=f.base.digest(Path(__file__)),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=f.ROOT,text=True).strip(),
        entropy_schedule='0.01 through 400000, linear to zero at 800000' if mode in ('entropy','combined') else 'constant 0.01',
        lane_reward='100m, +0.1 per newly crossed lane-error level per edge/target/episode' if mode in ('reward','combined') else 'none')
    f.save(d/'manifest.json',manifest);shutil.copy2(__file__,d/'runner.py')
    log=Log(d,agent,budget,env,name,smoke)
    try:
        agent.learn(env,budget,logger=log,eval_interval=0,exact_budget=True)
        assert agent.num_timesteps==budget and env.route_override_count==0
        agent.save(str(d/'model.pt'))
        f.save(d/'complete.json',dict(steps=budget,model_sha=f.base.digest(d/'model.pt'),action_overrides=0))
        f.save(d/'status.json',dict(stage='complete',step=budget,pid=os.getpid()))
    except Exception as exc:
        f.save(d/'status.json',dict(stage='error',error=repr(exc),pid=os.getpid()));raise
    finally:env.close();log.close()
    return name


def report():
    lines=['## 실행 결과','','각 셀은 동일한 62개 출발 조건의 완주 수다. 기준과 두 변경 조건 모두 같은 평가를 사용한다.','',
        '| 조건 / seed | 단계 | 완주 | 충돌 | 시간 초과 |','|---|---:|---:|---:|---:|']
    groups={}
    for path in sorted((OUT/'evaluations').glob('*/*.json')):
        r=f.read(path);rows=r['rows']
        groups.setdefault(path.parent.name,[]).append(r)
        lines.append(f"| {path.parent.name} | {r['step']} | {r['arrivals']}/{r['cases']} | {sum(x['collision'] for x in rows)} | {sum(x.get('timeout',False) for x in rows)} |")
    lines+=['','### 단계별 완주율 (3 seed 합계)','','| 단계 | 기존 | 탐험 감소 | 차로 보상 | 조합 |','|---:|---:|---:|---:|---:|']
    for step in sorted({r['step'] for records in groups.values() for r in records}):
        cells=[]
        for mode in ('baseline','entropy','reward','combined'):
            rs=[r for s in (11,22,33) for r in groups.get(f'{mode}-{s}',[]) if r['step']==step]
            cells.append(f"{100*sum(r['arrivals'] for r in rs)/sum(r['cases'] for r in rs):.2f}%" if len(rs)==3 else '평가 대기')
        lines.append('| '+str(step)+' | '+' | '.join(cells)+' |')
    lines+=['','### 변화 추적','','| 조건 / seed | 현재 단계 | 기준 대비 완주율 차이 | 관측 최고 단계 | 직전 대비 성공→실패 / 실패→성공 |','|---|---:|---:|---:|---:|']
    for name,records in sorted(groups.items()):
        records.sort(key=lambda r:r['step']);latest=records[-1]
        best=max(records,key=lambda r:r['arrivals'])
        ref=next((r for r in groups.get('baseline-'+name.split('-')[-1],[]) if r['step']==latest['step']),None)
        diff=f"{100*(latest['arrivals']/latest['cases']-ref['arrivals']/ref['cases']):+.2f}%p" if ref else '기준 평가 대기'
        lost=gained=0
        if len(records)>1:
            def key(r):return (r['route'],r['lane'],r['speed'])
            prev={key(r):r['arrival'] for r in records[-2]['rows']}
            lost=sum(prev[key(r)] and not r['arrival'] for r in latest['rows'])
            gained=sum(not prev[key(r)] and r['arrival'] for r in latest['rows'])
        lines.append(f"| {name} | {latest['step']} | {diff} | {best['step']} ({best['arrivals']}/{best['cases']}) | {lost} / {gained} |")
    lines+=['','### 최신 경로별 완주','','| 조건 / seed | 경로 | 완주 / 사례 |','|---|---|---:|']
    for name,records in sorted(groups.items()):
        latest=max(records,key=lambda r:r['step'])
        for route in f.ROUTES:
            cases=[r for r in latest['rows'] if r['route']==route]
            lines.append(f"| {name} | {route} | {sum(r['arrival'] for r in cases)}/{len(cases)} |")
    prefix=DOC.read_text(encoding='utf8').split('## 실행 결과')[0]
    DOC.write_text(prefix.rstrip()+'\n\n'+'\n'.join(lines)+'\n',encoding='utf8')
    rel=str(DOC.relative_to(f.ROOT))
    subprocess.run(['git','add','--',rel],cwd=f.ROOT,check=True)
    changed=subprocess.run(['git','diff','--cached','--quiet','--',rel],cwd=f.ROOT).returncode
    if changed:
        subprocess.run(['git','commit','--only','-m','Record lane-learning checkpoint comparisons','--',rel],cwd=f.ROOT,check=True)
        subprocess.run(['git','push','origin','main'],cwd=f.ROOT,check=True)


def checks():
    assert [entropy_at(s) for s in (0,400000,600000,800000)]==[.01,.01,.005,0.]
    p=ProgressReward()
    assert p.award('e',[0],2,2,80)==0
    assert p.award('e',[0],1,2,80)==0
    assert p.award('e',[0],2,1,101)==0
    assert p.award('e',[],2,1,80)==0
    assert p.award('e',[0],2,1,80)==.1
    assert p.award('e',[0],2,1,80)==0
    assert p.award('e',[0],1,0,80)==.1
    assert p.award('e',[0],1,0,80)==0
    print('Schedule and non-repeatable lane reward checks passed.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');p.add_argument('--check',action='store_true')
    p.add_argument('--combined',action='store_true')
    p.add_argument('--eval');p.add_argument('--step',type=int);p.add_argument('--reference',action='store_true');args=p.parse_args()
    if args.check:checks();return
    if args.eval:evaluate(args.eval,args.step,args.reference);return
    OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    completed=[];errors=[];last_count=0
    try:
        # Generate shared static files once before children start.
        f.prepare('none')
        modes=('combined',) if args.combined else ('entropy','reward')
        specs=[(m,s,args.smoke) for m in modes for s in ((11,) if args.smoke else (11,22,33))]
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
            pending={pool.submit(train,s):s for s in specs}
            while pending:
                done,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
                for task in done:
                    spec=pending.pop(task)
                    try:completed.append(task.result())
                    except Exception as exc:errors.append(dict(spec=spec,error=repr(exc)))
                count=len(list((OUT/'evaluations').glob('*/*.json')))
                if not args.smoke and count!=last_count:
                    report();last_count=count
                status_name=('combined-' if args.combined else '')+('smoke-status.json' if args.smoke else 'status.json')
                f.save(OUT/status_name,dict(stage='running' if pending else 'error' if errors else 'complete',pid=os.getpid(),completed=completed,errors=errors,pending=len(pending),updated=time.time()))
    finally:lock.unlink()


if __name__=='__main__':main()

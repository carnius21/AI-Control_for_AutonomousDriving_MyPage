"""Sequential gated traffic campaign with parallel seeds and isolated evaluations."""
import argparse, concurrent.futures, json, os, subprocess, sys, time, traceback
from pathlib import Path
from utils import resume_validation as r
b=r.b; f=r.f
OUT=f.ROOT/'results/traffic_continuation_20261112'
f.OUT=OUT
DOC=f.ROOT/'docs/experiments/ic-traffic-continuation-20261112.md'

def save(p,d):r.save(p,d)
def env(seed,load,variants=()):
 m=f.read(r.sources('combined',seed)/'manifest.json')['baseline_manifest']
 return r.c.ClarityEnv(str(f.prepare(load)),dict(b.ROAD_NEW,routes=b.MAN['routes']),dict(m['ego'],depart_lane='best',depart_speed='max'),dict(m['simulation'],warmup_steps=300),b.OBSERVATION,m['action'],m['reward'],dict(b.TRAFFIC,prefill={'enabled':False}),variants,seed,navigation=b.NAV,clarity='baseline')
def evaluate(directory,policy,target):
 m=f.read(directory/'manifest.json'); b.torch.set_num_threads(1)
 f.environment=lambda mode,seed,load='none',routes=None,variants=():env(seed,load,variants)
 a=b.PPO(obs_dim=47,act_dim=2,**m['hp']);a.load(str(policy))
 rows=f.evaluate(a,'N1',m['seed'],m['load'],f.ROUTES,20,tuple(m['variants']))
 save(target,rows)
 save(target.with_suffix('.summary.json'),dict(cases=len(rows),arrivals=sum(x['arrival'] for x in rows),collisions=sum(x['collision'] for x in rows),gate=f.gate(rows,f.ROUTES),model_sha=b.digest(policy)))
def eval_process(d,p,t):
 subprocess.run([sys.executable,'-X','utf8','-m','utils.traffic_continuation','--evaluate',str(d),str(p),str(t)],cwd=f.ROOT,check=True)
class Log(b.Log):
 def __init__(self,*args):super().__init__(*args);self.next_eval=100000
 def log_train(self,step,metrics,verbose=False):
  super().log_train(step,metrics,verbose)
  if step>=self.next_eval or step==self.budget:
   p=self.directory/f'policy-{step}.pt';self.agent.save(str(p))
   eval_process(self.directory,p,self.directory/f'eval-{step}.json')
   self.next_eval+=100000

def train(spec):
 seed,load,source,variants,budget,label=spec;b.torch.set_num_threads(1)
 d=OUT/'runs'/f'{label}-{seed}'
 if (d/'complete.json').exists():
  m=f.read(d/'manifest.json');f.verify_hashes(m['inputs']);assert b.digest(d/'model.pt')==f.read(d/'complete.json')['model_sha'];return str(d)
 if d.exists():raise RuntimeError('Partial run preserved: '+str(d))
 f.check_disk();d.mkdir(parents=True)
 hp=f.read(r.sources('combined',seed)/'manifest.json')['hp']
 m=dict(seed=seed,load=load,hp=hp,variants=list(variants),budget=budget,source=str(source),source_sha=b.digest(source),map_sha=b.digest(b.MAP/'network.net.xml'),commit=b.COMMIT,forced_correction=False)
 m['inputs']={str(f.ROOT/x):b.digest(f.ROOT/x) for x in r.c.SOURCES}
 m['inputs'][str(source)]=b.digest(source)
 save(d/'manifest.json',m)
 a=b.PPO(obs_dim=47,act_dim=2,buffer=b.RolloutBuffer(),**hp);a.load(str(source));a.save(str(d/'initial.pt'))
 if budget>2048:eval_process(d,d/'initial.pt',d/'initial-eval.json')
 e=env(seed,load,variants);log=Log(d,a,budget,e)
 try:
  a.learn(e,budget,logger=log,eval_interval=0,exact_budget=True)
  assert a.num_timesteps==budget and e.route_override_count==0
  a.save(str(d/'model.pt'))
 finally:e.close();log.close()
 f.verify_hashes(m['inputs'])
 import shutil
 shutil.copy2(d/f'eval-{budget}.json',d/'evaluation.json')
 shutil.copy2(d/f'eval-{budget}.summary.json',d/'evaluation.summary.json')
 save(d/'complete.json',dict(steps=budget,gate=f.gate(f.read(d/'evaluation.json'),f.ROUTES),model_sha=b.digest(d/'model.pt')))
 return str(d)

def report(stage):
 lines=['# 트래픽 후속 실험 자동 진행','',f'현재 단계: {stage}','','무교통 조합600064 모델(seed11/22/33)을 공통 출발점으로 사용. 강제 보정 없음. 관측47차원.','추가학습은 기존 설계대로 기본 PPO/보상/하이퍼파라미터, optimizer 새 초기화, 단계당800000스텝. 목적지 보상·탐험감소를 트래픽 단계에 동시에 추가하지 않음.','최대6작업 병렬. 매10만 스텝 평가 및 TensorBoard 기록. 최종800000 모델로 다음 단계 기준을 판정; 중간 최고 모델로 몰래 대체하지 않음.','','| 실행 | 평가 | 완주 | 충돌 | 통과 |','|---|---|---:|---:|---|']
 for p in sorted(OUT.glob('runs/*/*.summary.json')):
  x=f.read(p);lines.append(f"| {p.parent.name} | {p.stem} | {x['arrivals']}/{x['cases']} | {x['collisions']} | {x['gate']} |")
 lines+=['','기본수요 HV는 기존 재검증에서 미달: 13~15번의 공통 1차로 램프에 2250대/시간이 집중됨. 원래 수요와 통과 기준을 낮추지 않으며, 기본수요 의존 단계는 이 검증 통과 전 실행하지 않음.','ZIP 이벤트는 현 맵에서 미검증이므로 기존 설계대로 제외. 원자료는 로컬 results/traffic_continuation_20261112.']
 DOC.write_text('\n'.join(lines)+'\n',encoding='utf8')
 rel=str(DOC.relative_to(f.ROOT));subprocess.run(['git','add','--',rel],cwd=f.ROOT,check=True)
 if subprocess.run(['git','diff','--cached','--quiet','--',rel],cwd=f.ROOT).returncode:
  subprocess.run(['git','commit','--only','-m','Record traffic campaign: '+stage,'--',rel],cwd=f.ROOT,check=True)
  result=subprocess.run(['git','push','origin','main'],cwd=f.ROOT)
  save(OUT/'publication.json',dict(pending=result.returncode!=0,stage=stage))
def batch(specs,label):
 done=[];errors=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
  pending={pool.submit(train,s):s for s in specs}
  while pending:
   ready,_=concurrent.futures.wait(pending,timeout=30,return_when=concurrent.futures.FIRST_COMPLETED)
   for q in ready:
    spec=pending.pop(q)
    try:done.append(q.result())
    except Exception:errors.append(dict(spec=[str(x) for x in spec],traceback=traceback.format_exc()))
   save(OUT/'status.json',dict(stage=label,pid=os.getpid(),pending=len(pending),done=done,errors=errors,updated=time.time()))
   if ready:report(label)
 if errors:raise RuntimeError('Worker errors saved in status.json')
 return [Path(d) for d in done]
def diagnose(directory):
 import collections
 rows=f.read(directory/'evaluation.json')
 output=[]
 for route in f.ROUTES:
  group=[x for x in rows if x['route']==route]
  output.append(dict(route=route,cases=len(group),arrivals=sum(x['arrival'] for x in group),causes=dict(collections.Counter(x.get('failure','unknown') for x in group if not x['arrival']))))
 save(directory/'failure-analysis.json',output)

def main():
 p=argparse.ArgumentParser();p.add_argument('--evaluate',nargs=3);p.add_argument('--smoke',action='store_true');args=p.parse_args()
 if args.evaluate:evaluate(*map(Path,args.evaluate));return
 OUT.mkdir(parents=True,exist_ok=True);lock=OUT/'active.lock'
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for load in ['low','base']:f.prepare(load)
  sources={s:r.sources('combined',s)/'policy-600064.pt' for s in [11,22,33]}
  for s in sources:assert f.read(r.OUT/'jobs'/f'holdout-combined-{s}-600064'/'complete.json')['per_route_gate']
  for s in sources:
   v=f.read(r.OUT/'jobs'/f'holdout-combined-{s}-600064'/'manifest.json')
   assert v['evaluation_map_sha']==b.digest(b.MAP/'network.net.xml') and v['model_sha']==b.digest(sources[s])
  if args.smoke:
   batch([(11,'low',sources[11],(),2048,'smoke')],'smoke');return
  for load in ['low','base']:
   for s in [1001,1002,1003]:
    hv=f.read(r.OUT/'hv'/f'{load}-{s}.json');f.verify_hashes(hv['inputs'])
    assert b.digest(r.OUT/'traffic_v2'/f'{load}-hv'/'network.net.xml')==b.digest(b.MAP/'network.net.xml')
   if not all(f.read(r.OUT/'hv'/f'{load}-{s}.json')['pass'] for s in [1001,1002,1003]):
    save(OUT/'status.json',dict(stage='blocked_hv_'+load,reason='Original HV gate failed; dependent experiments not run'));report('blocked_hv_'+load);return
   ds=batch([(s,load,sources[s],(),800000,load) for s in sources],load)
   for d in ds:diagnose(d)
   if not all(f.read(d/'complete.json')['gate'] for d in ds):
    save(OUT/'status.json',dict(stage='blocked_av_'+load,reason='Per-route AV gate failed; completed comparisons retained'));report('blocked_av_'+load);return
   sources={f.read(d/'manifest.json')['seed']:d/'model.pt' for d in ds}
  batch([(s,'base',sources[s],v,800000,'reward-'+name) for s in sources for name,v in [('control',()),('ROUTE100',('ROUTE100',)),('RAMP',('RAMP',))]],'reward-comparison')
  save(OUT/'status.json',dict(stage='planned_comparisons_complete',zipper='requires event validation'));report('planned_comparisons_complete')
 except Exception:
  save(OUT/'fatal.json',dict(traceback=traceback.format_exc()));raise
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

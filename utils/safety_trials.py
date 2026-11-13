"""Bounded independent safety-reward trials following collision diagnosis."""
import argparse,concurrent.futures,os,subprocess,sys,time
from pathlib import Path
from utils import traffic_continuation as t
b=t.b;f=t.f
OUT=f.ROOT/'results/safety_trials_20261113';t.OUT=OUT;f.OUT=OUT
DOC=f.ROOT/'docs/experiments/ic-safety-trials-20261113.md'
original_env=t.env

def environment(seed,load,variants=()):
 e=original_env(seed,load,())
 e.rw=dict(e.rw)
 if 'GAP15' in variants:e.rw['time_gap_s']=1.5
 if 'COLLISION20' in variants:e.rw['collision_penalty']=20.
 return e
t.env=environment

def eval_process(d,p,target):
 subprocess.run([sys.executable,'-X','utf8','-m','utils.safety_trials','--evaluate',str(d),str(p),str(target)],cwd=f.ROOT,check=True)
t.eval_process=eval_process

def report(stage):
 lines=['# 충돌 진단 후 보상 독립 비교','',f'상태: {stage}','','기존 저수요800k 결과를 대조군으로 보존한다. 동일한 무교통 조합600064 가중치(seed11/22/33)에서 다시 시작하며 optimizer 새 초기화, 각800k, 맵/교통/관측47/행동/PPO 고정. 강제보정 없음.','GAP15: 기존 고정6m 근접 기준만 2.5+속도×1.5초로 변경. 기존0.1벌점 유지. COLLISION20: 충돌벌점만5→20. 두항목을 섞지 않음.','사전 관측검사→각2048스텝 실행검증→6개독립 학습→10만마다320회평가→경로별분석→보고서순으로 자동진행. 모델선택/후속수요 진행은 결과확인전 하지않음. ZIP/기본수요실패는 미해결로 유지.','','|실험|평가|완주|충돌|경로별통과|','|---|---|---:|---:|---|']
 for p in sorted(OUT.glob('runs/*/*.summary.json')):
  d=f.read(p);lines.append(f"|{p.parent.name}|{p.stem}|{d['arrivals']}/{d['cases']}|{d['collisions']}|{d['gate']}|")
 DOC.write_text('\n'.join(lines)+'\n',encoding='utf8')
 rel=str(DOC.relative_to(f.ROOT));subprocess.run(['git','add','--',rel],cwd=f.ROOT,check=True)
 if subprocess.run(['git','diff','--cached','--quiet','--',rel],cwd=f.ROOT).returncode:
  subprocess.run(['git','commit','--only','-m','Record safety trials: '+stage,'--',rel],cwd=f.ROOT,check=True)
  x=subprocess.run(['git','push','origin','main'],cwd=f.ROOT)
  t.save(OUT/'publication.json',dict(pending=x.returncode!=0))
t.report=report

def audit():
 import numpy as np
 e=environment(11,'low');m=f.read(t.r.sources('combined',11)/'manifest.json');a=b.PPO(obs_dim=47,act_dim=2,**m['hp']);a.load(str(t.r.sources('combined',11)/'policy-600064.pt'));samples=[]
 try:
  o,_=e.reset(seed=40001,options={'route':'route_01'})
  for _ in range(100):
   lead=e._neighbor(0,True);speed=b.traci.vehicle.getSpeed(e.ego_id);idx=1+4*list(e.obs_offsets).index(0)
   expected=[1.,1.] if lead is None else [min(1.,lead[0]/e.visibility),float(np.clip((lead[1]-speed)/e.vmax,-1,1))]
   assert np.allclose(o[idx:idx+2],expected,atol=1e-6),(o[idx:idx+2],expected)
   samples.append(dict(step=e.step_count,gap=None if lead is None else lead[0],speed=speed,observed=o[idx:idx+2].tolist(),expected=expected))
   o,_,done,cut,_=e.step(a.predict(o,deterministic=True))
   if done or cut:break
 finally:e.close()
 t.save(OUT/'observation-audit.json',dict(passed=True,scope='same-lane distance/relative-speed encoding, route01 seed40001 only',samples=samples))
 for variant in ['GAP15','COLLISION20']:
  e=environment(11,'low',(variant,))
  assert e.rw.get('time_gap_s')==1.5 if variant=='GAP15' else e.rw['collision_penalty']==20.
  e.close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--evaluate',nargs=3);p.add_argument('--audit',action='store_true');args=p.parse_args()
 if args.evaluate:t.evaluate(*map(Path,args.evaluate));return
 OUT.mkdir(parents=True,exist_ok=True);fd=os.open(OUT/'active.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  f.prepare('low');audit()
  script_sha=b.digest(Path(__file__))
  t.save(OUT/'runner-manifest.json',dict(script_sha=script_sha,commit=b.COMMIT,map_sha=b.digest(b.MAP/'network.net.xml')))
  if args.audit:return
  report('observation-audit-passed')
  source=lambda s:t.r.sources('combined',s)/'policy-600064.pt'
  t.batch([(11,'low',source(11),(v,),2048,'smoke-'+v) for v in ['GAP15','COLLISION20']],'smoke')
  ds=t.batch([(s,'low',source(s),(v,),800000,v) for v in ['GAP15','COLLISION20'] for s in [11,22,33]],'independent-training')
  assert b.digest(Path(__file__))==script_sha
  for d in ds:t.diagnose(d)
  t.save(OUT/'status.json',dict(stage='planned_trials_complete',runs=[str(d) for d in ds],not_equivalent_to_target_achieved=True));report('planned_trials_complete')
 finally:(OUT/'active.lock').unlink(missing_ok=True)
if __name__=='__main__':main()

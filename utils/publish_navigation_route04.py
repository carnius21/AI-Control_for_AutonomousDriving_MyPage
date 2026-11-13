"""Publish compact route04 results as the existing sequential runner finishes runs.
Does not launch/restart training or alter any experiment condition.
"""
import json,time,os,hashlib,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/navigation_route04_v1'
DOC=ROOT/'docs/ic-navigation-route04-results.md'
ROUTE_LABEL='04'

def read(p):return json.loads(p.read_text(encoding='utf8'))
def save(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8');t.replace(p)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf8',stderr=subprocess.STDOUT).strip()
def publish():
 rows=[]
 for directory in sorted((OUT/'runs').glob('*')):
  if not (directory/'complete.json').exists():continue
  d=read(directory/'complete.json');m=read(directory/'manifest.json');ev=read(directory/'evaluation.json');audit=read(directory/'action-audit.json')
  assert d['steps']==200000 and len(ev)==20 and audit['route_override_count']==0 and audit['checked_steps']==200000
  assert all(r.get('route_overrides',0)==0 for r in ev)
  assert hashlib.sha256((directory/'snapshot/maps/toegyewon_only/network.net.xml').read_bytes()).hexdigest()==m['network_sha256']
  assert m['action_overrides'] is False
  rows.append(dict(mode=d['mode'],seed=d['seed'],arrival=sum(r['arrival'] for r in ev),collision=sum(r['collision'] for r in ev),timeout=sum(r.get('timeout',False) for r in ev),insertion=sum(r.get('insertion_failure',False) for r in ev),teleports=sum(r.get('teleports',0) for r in ev),initial=d['initial_sha'],git=m['git'],path=str(directory.relative_to(ROOT)),model_sha=hashlib.sha256((directory/'model.pt').read_bytes()).hexdigest()))
 for seed in (11,22,33):assert len({r['initial'] for r in rows if r['seed']==seed})<=1
 prior=read(OUT/'publisher.json') if (OUT/'publisher.json').exists() else {}
 if prior.get('runs')==len(rows):return
 lines=['# 04번 순수 PPO 관측 비교 결과','','학습·평가는 강제 차로 보정 없이 실행한다. 동일 조건별200,000스텝, seed11/22/33. 각 모델은 출발차로4개×속도5개인20조건으로 검증한다. 이 표는 검증 결과이며 최종100회holdout평가나16경로전체/HV평가가 아니다.','',f'완료: **{len(rows)}/9개 모델**. 미완료 조건은 결과를 추정하지 않는다.','','| 관측 | 학습 seed | 완주 | 충돌 | 시간초과 | 삽입 실패 |','|---|---:|---:|---:|---:|---:|']
 for r in rows:lines.append(f"| {r['mode']} | {r['seed']} | {r['arrival']}/20 | {r['collision']} | {r['timeout']} | {r['insertion']} |")
 lines+=['','N0=기존 관측, N1=정적 경로 안내, N2=N1+경로별 차로 연결성. 모든완료run에서200,000스텝행동검사·override0·맵스냅샷해시·20평가사례를확인했다. 같은seed의초기모델해시일치도검사했다.','','## 반복 평균 (세 seed 모두 완료된 조건만)','','| 조건 | 완주율 | 충돌률 |','|---|---:|---:|']
 for mode in ('N0','N1','N2'):
  group=[r for r in rows if r['mode']==mode]
  if len(group)==3:lines.append(f"| {mode} | {sum(r['arrival'] for r in group)/60:.1%} | {sum(r['collision'] for r in group)/60:.1%} |")
 lines+=['','## 실행 근거','','| 조건/seed | 실행 커밋 | 로컬 결과 | 모델 SHA256 |','|---|---|---|---|']
 for r in rows:lines.append(f"| {r['mode']}/{r['seed']} | `{r['git'][:7]}` | `{r['path']}` | `{r['model_sha']}` |")
 lines+=['','[설계](ic-navigation-learning-plan.md) · [구현·검증](ic-navigation-route04-progress.md)','','모델·원시JSON·TensorBoard는로컬results에만저장한다. 이표는완료이벤트마다자동갱신한다.14번이후단계나보상/학습률변경은이자동화에포함하지않는다.']
 DOC.write_text(('\n'.join(lines)+'\n').replace('04번',ROUTE_LABEL+'번').replace('ic-navigation-route04-progress.md','ic-navigation-route'+ROUTE_LABEL+'-progress.md').replace('14번이후단계','다음경로단계'),encoding='utf8')
 git('add',str(DOC.relative_to(ROOT)))
 if git('diff','--cached','--name-only','--',str(DOC.relative_to(ROOT))):
  git('commit','--only','-m',f'Record route{ROUTE_LABEL} navigation comparison: {len(rows)} of 9 completed','--',str(DOC.relative_to(ROOT)))
  git('push','origin','main')
 save(OUT/'publisher.json',dict(runs=len(rows),stage='complete' if len(rows)==9 else 'monitoring',updated=time.time()))
 print(f'Published {len(rows)}/9 completed runs',flush=True)

def main():
 lock=OUT/'publisher.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  while True:
   if shutil.disk_usage(OUT).free<12*1024**3:raise RuntimeError('Disk free below 12GiB')
   state=read(OUT/'status.json')
   publish()
   if state['stage']=='train_complete':break
   if state['stage']=='error':raise RuntimeError(state.get('error','Training failed'))
   if not (OUT/'active.lock').exists():raise RuntimeError('Training runner inactive before completion')
   # No timer delay between training jobs: only status publication is polled.
   time.sleep(15)
 except Exception as e:
  save(OUT/'publisher-error.json',dict(error=repr(e),time=time.time()));raise
 finally:lock.unlink()
if __name__=='__main__':main()

from collections import Counter
import json
from pathlib import Path
p=Path(__file__).resolve().parent
names={"control":"A0 그대로","gap":"음수 간격 관측 수정","brake":"관측 수정 + 미감속 벌점"}
keys=["arrival","collision","front","timeout","risk","brake_cmd","response_observed","decelerated","neg_gap","penalties","unknown","visible_risk"]
data={}
out=["# 전방 추돌 실험 · 고교통 48회","","A0 60만 스텝에서 고교통으로 추가 학습. 학습 seed 11, 세 조건 동일 평가 경로와 교통 seed, 안전게이트 없음. 매 모델 16경로 × 3회. 위험 기준은 앞차에 0.5m/s 넘게 접근하고 TTC가 2.5초 미만인 스텝. 유효 차량의 음수 간격은 위험 집계에서 세 조건 모두 0m로 처리. 실제 감속은 다음 속도를 확인할 수 있는 위험 스텝에서 속도가 0.01m/s 넘게 감소한 경우.","","|추가 스텝|조건|완주|모든 충돌|전방 추돌|시간초과|위험 시 감속 명령|위험 시 실제 감속|음수 간격 표본|추가 벌점 횟수|","|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
for mark in (0,10000,20000,30000,40000,50000,75000,100000,150000):
 for arm in names:
  f=p/arm/f"eval_{mark}.json"
  if not f.exists():continue
  rows=json.loads(f.read_text())
  assert {(i["route"],i["seed"]) for i in rows}=={(f"route_{i+1:02}",41001+i+100*j) for i in range(16) for j in range(3)}
  c=Counter()
  for r in rows:
   c[r["outcome"]]+=1
   if r["kind"]:c[r["kind"]]+=1
   c.update(r["metrics"])
  assert c["arrival"]+c["collision"]+c["timeout"]==48
  data[f"{arm}_{mark}"]={k:c[k] for k in keys}
  def ratio(k,n):
   return f"{c[k]}/{c[n]} ({100*c[k]/max(1,c[n]):.1f}%)"
  out.append(f"|{mark:,}|{names[arm]}|{c['arrival']}|{c['collision']}|{c['front']}|{c['timeout']}|{ratio('brake_cmd','risk')}|{ratio('decelerated','response_observed')}|{c['neg_gap']}|{c['penalties']}|")
print("\n".join(out[5:]))
(p/"비교결과.md").write_text("\n".join(out),encoding="utf8")
(p/"comparison.json").write_text(json.dumps(data,indent=2))


from pathlib import Path
import json,gzip,collections,xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
net=ET.parse(P.parent/"A2_11"/"eval_maps"/"high_real_ratio"/"network.net.xml")
counts={e.get("id"):len(e.findall("lane")) for e in net.findall("edge")}
def read(path):return json.loads(path.read_text())
def sign(x):return "+" if x>0 else "−" if x<0 else "0"
def direction(x):return {1:"좌",0:"유지",-1:"우"}[x]
def front(f):
 g,rv=f["obs"][9:11]
 return (None,None) if g==1 and rv==1 else (50*g,27.8*rv)
def fmt(x):return "없음" if x is None else f"{x:.1f}"
out=["# 실험 A 충돌 48건 재현 기록","","고교통, 학습 seed 11, 60만 스텝 최종 모델. 모든 재현은 기존 충돌과 경로·평가 seed·종료 유형이 일치했다. 아래 값은 충돌을 일으킨 0.2초 스텝의 직전 관측과 해당 스텝에 낸 명령이다. 원본 파일은 충돌 이전 최대 5초를 담는다.","","앞 간격과 상대속도는 정책의 현재 차로 앞차 입력을 역정규화했다. 간격은 SUMO 기반 입력으로 범퍼 실측 거리와 다를 수 있다. Δv는 앞차 속도 − AV 속도(m/s)다. 가감속은 정책 원본 명령(−1~+1). 실감속은 그 직전 0.2초 두 속도 표본의 차이가 −0.01m/s 미만인 경우다. 마지막 프레임의 차선변경 명령 접수는 충돌 스텝의 이동 성공과 구분한다.","","전방은 AV가 SUMO 충돌 유발 차량이며, 상대가 직전 선행 차량이고 같은 차로 또는 진행 연결로에 있었던 경우다. junction 중 동일 내부 차로에서 선행 차량을 추돌한 A3·41211도 전방으로 분류했다. 다른 내부 경로가 만나는 junction은 합류, 명시적 side는 측면으로 분류했다. 위험 시도는 유효한 목표 차로로 새 변경 시도를 냈을 때만 목표 차로의 겹침 또는 2초 미만 접근시간을 센다.",""]
for a in ("A2","A3"):
 stats=collections.Counter(); categories=collections.Counter()
 out.extend([f"## {a} 24건","","|경로·seed|유형|앞 간격 m / Δv|좌·우 겹침|가감속|직전 실감속|차선 명령·접수|위험 분류 근거|","|---|---|---|---|---:|---|---|---|"])
 for row in read(P/f"{a}_600000_crashes.json"):
  frames=json.load(gzip.open(P/f"{a}_{row['route']}_{row['seed']}.json.gz","rt"))
  z=frames[-1]; ego=z["vehicles"]["ego"];c,=row["collisions"]; hv=c["victim"] if c["collider"]=="ego" else c["collider"];oth=z["vehicles"][hv]
  edge,ln=ego[0].rsplit("_",1);d=z["lane_change"]
  if c["type"]=="side": kind="측면"
  elif c["collider"]!="ego":kind="후방 피추돌"
  elif c["type"]=="junction" and ego[0]!=oth[0]:kind="합류 교차"
  else:
   assert z["leader"] and z["leader"][0]==hv
   kind="전방 추돌"
  categories[kind]+=1
  gap,rv=front(z)
  slow=None if len(frames)==1 else ego[2]-frames[-2]["vehicles"]["ego"][2]<-.01
  reason="유지 명령" if not d else "교차로 내부" if edge.startswith(":") else "옆 차로 없음" if not 0<=int(ln)+d<counts[edge] else "연속 명령·도로 제약" if not z["attempt"] else "변경 시도, 목표 쪽 위험 기준 미달" if not z["risk"] else "위험 감지"
  if kind=="측면":
   fg=z["sides"][str(d)][0]
   reason+=f" (옆 앞간격 {fg[0]:.2f}m, Δv {fg[1]-ego[2]:+.1f})"
  if kind=="전방 추돌":
   stats["visible"]+=gap is not None
   stats["brake"]+=z["accel_raw"]<0
   stats["actual"]+=bool(slow)
   warnings=[f for f in frames[-10:] if front(f)[0] is not None and front(f)[1]<-.5 and front(f)[0]/(-front(f)[1])<2.5]
   stats["warned"]+=bool(warnings)
   stats["ever_braked_warned"]+=any(f["accel_raw"]<0 for f in warnings)
  stats["attempt"]+=z["attempt"];stats["risk"]+=z["risk"]
  out.append(f"|{row['route'][-2:]} · {row['seed']}|{kind}|{fmt(gap)} / {fmt(rv)}|{int(z['obs'][-1])}·{int(z['obs'][-2])}|{z['accel_raw']:+.2f}|{('예' if slow else '아니오') if slow is not None else '첫 스텝'}|{direction(d)} · {('접수' if z['lane_change_applied'] else '미접수') if d else '—'}|{reason}|")
 print(a,categories,stats)
 out.append("")
(P/"충돌48건.md").write_text("\n".join(out),encoding="utf-8")
out.extend(["## 충돌 직전 좌우 차로 입력과 전방 경고","","정책에 전달된 좌·우 인접 차로의 앞/뒤 간격(m), 현재 차로 뒤차 간격을 역정규화했다. —는 센서 입력의 차량 없음 표시다. 경고는 분석용으로 정책 입력에서 앞차에 0.5m/s 넘게 접근하며 예상 충돌시간이 2.5초 미만인 표본이다. 횟수는 마지막 2초(최대 10표본) 기준이다. 차로 변경에 쓴 별도 측면 스캔은 이 정책 입력과 다를 수 있다.","","|조건·경로·seed|좌측 앞/뒤 m|현재 뒤 m|우측 앞/뒤 m|경고 표본 중 감속 명령 / 경고 표본|","|---|---:|---:|---:|---:|"])
for a in ("A2","A3"):
 for case in read(P/f"{a}_600000_crashes.json"):
    frames=json.load(gzip.open(P/f"{a}_{case['route']}_{case['seed']}.json.gz","rt"));obs=frames[-1]["obs"]
    def obs_gap(idx,rear=False):
        null=-1 if rear else 1
        return "—" if obs[idx:idx+2]==[null,null] else f"{abs(obs[idx])*50:.1f}"
    warning=[f for f in frames[-10:] if front(f)[0] is not None and front(f)[1]<-.5 and front(f)[0]/(-front(f)[1])<2.5]
    out.append(f"|{a} · {case['route'][-2:]} · {case['seed']}|{obs_gap(5)} / {obs_gap(7,True)}|{obs_gap(11,True)}|{obs_gap(13)} / {obs_gap(15,True)}|{sum(f['accel_raw']<0 for f in warning)} / {len(warning)}|")
(P/"충돌48건.md").write_text("\n".join(out),encoding="utf-8")

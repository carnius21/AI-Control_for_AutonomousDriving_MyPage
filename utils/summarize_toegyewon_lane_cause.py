"""Summarize paired AV diagnostics without conflating rule assistance with PPO learning."""
import json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
def main():
 dest=ROOT/'results/toegyewon_lane_cause_v1'
 files=sorted((dest/'cases').glob('*.json'));rows=[json.loads(p.read_text(encoding='utf8')) for p in files]
 assert len(rows)==128
 baseline=[r for r in rows if r['mode']=='baseline'];summary={}
 for mode,n in [('baseline',16),('route_observation',16),('route_guidance',48),('route_guard',48)]:
  subset=[r for r in rows if r['mode']==mode];assert len(subset)==n
  summary[mode]=dict(cases=n,arrivals=sum(r['arrival'] for r in subset),collisions=sum(r['collision'] for r in subset),teleports=sum(r['teleports'] for r in subset))
 old=[json.loads(p.read_text()) for p in (ROOT/'results/toegyewon_only_v2/av').glob('*.json')]
 ref={(r['route'],r['training_seed']):r for r in old}
 for r in rows:
  o=ref[r['route'],r['training_seed']]
  assert (r['policy_sha256'],r['network_sha256'],r['simulation_seed'])==(o['policy_sha256'],o['network_sha256'],o['simulation_seed'])
 counts=Counter();failures=[]
 for r in baseline:
  last=r['diagnostic']['samples'][-1];s=r['edges'][last['edge']];counts.update(s['wrong_moving'])
  failures.append(dict(route=r['route'],seed=r['training_seed'],edge=last['edge'],lane=last['lane_index'],target_lanes=last['allowed_lanes'],moving_wrong=s['wrong_moving'],stopped_wrong=s['wrong_stopped'],left_valid_lane=s['departures_from_valid_lane']))
 lines=['# 퇴계원 AV 차로 선택 실패: 원인 분리와 보정 비교','','## 결론','','실패했던 11개 경로·16개 정책 사례를 전부 재현했다. 실패 지점에서 올바른 복귀 명령이 실선/안전 게이트 때문에 막힌 패턴은 확인되지 않았다. 잘못된 차로에서 다음 연결부까지 10m 초과가 남은 319스텝 중 반대 방향308, 유지11, 올바른 방향0이었다. 이319스텝 모두 기존 best-lane offset은 복귀 방향과 일치했지만 분기 거리/방향 관측은 누락돼 있었다. 입력 일부의 누락과 정책의 잘못된 선택이 동시에 존재하며, 정보가 전혀 없었다고 표현하면 틀린다.','','반대 방향308 중306은 도로 바깥으로 나가는 명령이라 거부됐고2는 실제 명령 제출이었다. 이전의 단순 rejected 횟수는 이런 잘못된 명령까지 섞어 세었으므로 안전 제한이 학습을 막았다는 근거가 되지 않는다. 이번 기록은 명령 제출(submitted)과 같은 도로 내 실제 차로 변화(actual_change_same_edge)를 구분한다.','','## 전후 비교','','| 조건 | 대상 | 완주 | 충돌 | 해석 |','|---|---:|---:|---:|---|','| 기존 PPO (직전 전체 평가) | 48 | 32 | 0 | 기준 |','| 실패 사례 기본 PPO 재현 | 16 | 0 | 0 | 이전 실패 일치 |','| 경로 관측만 수정, 기존 가중치 | 16 | 1 | 0 | 입력 민감도 시험, 재학습 아님 |','| 차로 명령 전체를 best-lane 안내로 교체 | 48 | 47 | 0 | 가감속은 PPO, 규칙 기반 차로 안내 |','| 목적지 차로 이탈/복귀만 최소 보정 | 48 | 48 | 0 | PPO+경로 보정, 순수 PPO 아님 |','','최소 보정은 이전 실패16/16을 해결하고 기존 성공32/32도 유지했다. 전체 완주율은66.7%→100%(+33.3%p). 단일 시뮬레이션 seed·무교통 조건의 기능 검증이며 새로운 교통/seed에 대한95% 성공률 보장이나 최종 학습 목표 달성을 주장하지 않는다.','','## 모든 실패 사례','','차로 번호는 SUMO 기준으로 주행 방향 오른쪽이0이다.','', '| 경로 | 정책 seed | 정지 도로 | 실제 차로 → 필요한 차로 | 접근 중 반대/유지/올바른 명령 |','|---|---|---|---|---|']
 for f in failures:
  c=f['moving_wrong'];lines.append(f"| {f['route']} | {f['seed']} | `{f['edge']}` | {f['lane']} → {','.join(map(str,f['target_lanes']))} | {c.get('away',0)}/{c.get('hold',0)}/{c.get('toward',0)} |")
 lines+=['','04의 seed11은1063527748에서0번 차로에 남아 있지만 목적지 연결은2번이다. seed22/33은170059994에서 원래 유효한 차로를 떠나3번으로 이동해 멈춘다. 14는 세 정책 모두170059994의3번에서 멈췄으며 목적지 차로는0/1/2번이다. 둘 다 현재 실선 금지 도로 목록에 없고, 올바른 방향의 차로 안내로는 동일 안전 제약에서 통과한다.','','나머지 실패도 두 부류다. 02·03·05·13·16은 분기에서 경로에 맞는 차로를 선택하지 못했고, 06·08·10·11은 종료되는 보조차로0에서 본선 차로로 복귀하지 못했다. 구체 위치와 정책별 횟수는 위 표와 원자료를 참조한다.','','## 관측·제어 수정 범위','','관측 수정은 진단용 ProbeEnv의 route_observation 모드에만 구현했다. 현재 도로의 경로별 연결 차로 집합과 남은 거리를 분기 특성으로 표현하고, 차로 연결성도 아무 도로 연결이 아니라 지정 경로 연결 여부를 반영했다. 관측 차원은 유지했다. 원래 로직은 목표가0번 차로 하나인 특정 분기만 안내하고, 다른 목적지로 연결되는 차로도 연결성1로 표시했다. 수정 관측은 재학습하지 않은 가중치에 넣은 민감도 시험이므로, 실패가 남았다고 관측 개선 자체가 무효라는 결론을 내리지 않는다. 통과로 바뀐 것은13번 seed33 하나다.','','최소 보정(route_guard)은 현재 경로와 연결되지 않은 차로면 가장 가까운 연결 차로 방향을 명령하고, 연결 차로 안에 있으면 그 집합을 벗어나는 명령만 유지로 바꾼다. 나머지 PPO 차로 명령과 모든 가감속을 보존하고 실선·안전 제한은 그대로 통과해야 한다. 기본 학습 환경의 정책/보상/안전 제한은 변경하지 않았으며 보정은 독립 실험 옵션에만 있다.','','전체 차로 안내(route_guidance)는 기존 실패16건은 전부 해결했지만, 기존에 통과하던13번 seed11을 정지시켰다. 해당 사례는 올바른1번 차로에서 가감속 raw=-0.523으로 정지했다. 차로 경로가 바뀐 뒤 PPO가 제동을 선택한 사례로, 원래 차로 실패와 구분한다. 최소 보정은 이 회귀도 없었다.','','## 증거·재현','','- 기존 정책: R0 seed11/22/33,200,000스텝 체크포인트. 모든 사례의 정책·맵 해시와 simulation seed1001 일치 검사 완료.','- best/max 출발, 무교통, 결정적 행동, 최대900초. 128사례와1초 간격 관측/명령/거부 사유 추적을 보존.','- 실행: `python -m utils.diagnose_toegyewon_lane_cause`','- 요약 재생성: `python -m utils.summarize_toegyewon_lane_cause`','- 원시 결과: `results/toegyewon_lane_cause_v1/cases`, `traces`','- [요약 수치·실행 커밋·파일 해시](experiments/toegyewon-lane-cause-v1.json)','','다음 순수 강화학습 비교에서는 기존 관측과 수정 관측을 동일 경로/초기화seed/스텝/보상으로 각각 처음부터 학습해야 한다. 이번48/48을 PPO의 재학습 성능으로 사용하지 않는다.']
 (ROOT/'docs/ic-toegyewon-lane-cause-results.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 compact=[]
 for p,r in zip(files,rows):
  compact.append({k:v for k,v in r.items() if k not in ('edges','diagnostic')}|dict(result_file=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),last_sample=r['diagnostic']['samples'][-1]))
 report=dict(summary=summary,failed_approach_counts=dict(counts),failures=failures,cases=compact)
 (ROOT/'docs/experiments/toegyewon-lane-cause-v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()

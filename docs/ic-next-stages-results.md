# 수정 맵 후속 실험 결과

현재 단계: **blocked: shared policy gate**

합성 수요이며 실측 교통량이 아니다. 강제 경로 보정은 사용하지 않는다. [실험 조건·통과 기준](ic-next-stages-plan.md).

## HV 단독 검증

| 수요/seed | 예정/삽입/도착 | 충돌 차량 누계 | 텔레포트 | 통과 |
|---|---|---:|---:|---|
| base/1001 | 2552/2342/2315 | 0 | 0 | False |
| base/1002 | 2552/2347/2319 | 0 | 0 | False |
| base/1003 | 2552/2344/2314 | 0 | 0 | False |
| low/1001 | 1278/1278/1278 | 0 | 0 | True |
| low/1002 | 1278/1278/1278 | 0 | 0 | True |
| low/1003 | 1278/1278/1278 | 0 | 0 | True |

## AV 평가 (완료된 평가만)

| 실행 | 경로 | 완주/횟수 | 충돌 | 시간초과 | 원인 분류 |
|---|---|---|---:|---:|---|
| frozen\route_04-N0-11-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N0-22-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N0-33-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N1-11-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N1-22-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N1-33-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N2-11-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N2-22-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_04-N2-33-low | route_04 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N0-11-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N0-22-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N0-33-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N1-11-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N1-22-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N1-33-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N2-11-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N2-22-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| frozen\route_14-N2-33-low | route_14 | 0/5 | 5 | 0 | {'collision': 5} |
| runs\shared-N0-11 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_02 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N0-11 | route_03 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_04 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_10 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_11 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_13 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_14 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-11 | route_16 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_02 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_03 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_04 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_10 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N0-22 | route_11 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N0-22 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_13 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_14 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-22 | route_16 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_02 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N0-33 | route_03 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_04 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_10 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_11 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_13 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_14 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N0-33 | route_16 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_02 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_03 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N1-11 | route_04 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N1-11 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_10 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_11 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_13 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N1-11 | route_14 | 0/20 | 0 | 20 | {'route_lane_blocked': 20} |
| runs\shared-N1-11 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-11 | route_16 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_02 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_03 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_04 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_10 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_11 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_13 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_14 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-22 | route_16 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_01 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_02 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_03 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_04 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_05 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_06 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_07 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_08 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_09 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_10 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_11 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_12 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_13 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_14 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_15 | 20/20 | 0 | 0 | {} |
| runs\shared-N1-33 | route_16 | 20/20 | 0 | 0 | {} |

## 보상 진단 (완료된 평가)

| 실행 | 준비 성공/판정 | 과속/램프 스텝 | 보상 성분 합 |
|---|---:|---:|---|
| shared-N0-11 | 240/500 | 32405/121684 | {'base': 3161.876902921448, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |
| shared-N0-22 | 420/500 | 35246/36591 | {'base': 3228.2219460323763, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |
| shared-N0-33 | 380/500 | 32298/121857 | {'base': 3160.606605486663, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |
| shared-N1-11 | 262/420 | 31847/380121 | {'base': 3009.4545208604163, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |
| shared-N1-22 | 296/500 | 35527/36238 | {'base': 3372.9128795208767, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |
| shared-N1-33 | 420/500 | 35829/35877 | {'base': 3374.9568720576954, 'route': 0.0, 'zipper': 0.0, 'ramp': 0.0} |

각 run의 manifest에 실행 커밋·seed·맵/코드/모델 해시·설정·선행 모델을 보존한다. 모델과 사례 추적은 로컬 results/navigation_followup_v2에만 저장한다.

현재 맵의 우선권을 유지했다. 옛 사노 지퍼 이벤트는 적용되지 않으므로 ZIP 보상은 검증 대기다. 평가 미달 이후 단계는 자동 차단한다.

> **과거 기록** — 작성 당시의 설계·맵·결과입니다. 현재 적용 기준은 [최신 문서 목록](../README.md)을 확인하세요.

# 학습 파라미터 비교 결과

## 학습률 0.0001, seed11 (2026-11-07)

기본 보상을 유지하고 학습률만 0.0003에서 0.0001로 줄였다. 20만 스텝 최종 정책, 교통 seed1001~1005 × 22경로 = 110회 평가. 완주 20회(18.2%), 충돌 11회(10.0%), 시간 초과 79회(71.8%). 기본 seed11의 55/35/20회 대비 완주 −31.8%p, 충돌 −21.8%p, 시간 초과 +53.6%p.

낮은 충돌률만으로 개선이라고 판단할 수 없으며 같은 학습량에서는 완주가 크게 감소했다. 작은 학습률에서 업데이트가 부족했을 가능성은 가설이며 추가 학습량 비교 없이 확정할 수 없다. 다른 seed 반복과 시간 초과 원인 분류가 필요하다. seed22 학습이 자동 시작됐다.

|경로|기본 완주/충돌/시간초과|학습률 변경 완주/충돌/시간초과|
|---|---|---|
|east_through|2 / 3 / 0|0 / 3 / 2|
|east_to_north|5 / 0 / 0|5 / 0 / 0|
|east_to_south|5 / 0 / 0|5 / 0 / 0|
|north_through|3 / 2 / 0|0 / 2 / 3|
|north_to_east|4 / 1 / 0|0 / 0 / 5|
|north_to_local|4 / 1 / 0|5 / 0 / 0|
|north_to_west|2 / 1 / 2|0 / 0 / 5|
|outer_to_south|5 / 0 / 0|5 / 0 / 0|
|sano_east_to_south|4 / 1 / 0|0 / 0 / 5|
|sano_north_through|2 / 3 / 0|0 / 0 / 5|
|sano_north_to_west|2 / 3 / 0|0 / 0 / 5|
|sano_south_through|4 / 1 / 0|0 / 0 / 5|
|sano_south_to_east|5 / 0 / 0|0 / 0 / 5|
|sano_south_to_west|3 / 2 / 0|0 / 0 / 5|
|sano_west_to_north|0 / 2 / 3|0 / 2 / 3|
|sano_west_to_south|0 / 2 / 3|0 / 2 / 3|
|south_through|0 / 2 / 3|0 / 2 / 3|
|south_to_east|0 / 3 / 2|0 / 0 / 5|
|south_to_local|0 / 3 / 2|0 / 0 / 5|
|south_to_west|2 / 3 / 0|0 / 0 / 5|
|west_through|3 / 2 / 0|0 / 0 / 5|
|west_to_local|0 / 0 / 5|0 / 0 / 5|

실행 경로 `results/ic_campaign_v2/runs/H-LR-11-200000`. 재개 기록 커밋 `029e3fd43b119a17d4cbc8fb4d04e9f76ad697c5`. 초기 학습 시작 manifest는 9e73f12였으나 재개 시 덮어써진 한계가 있다. 정책은 보존해 재사용했고 029e3fd는 진단 계측 추가다. 원본 `eval-200000.json`, 설정 `complete.json`.

## 학습률 0.0001, seed22 (2026-11-07)

기본 보상과 나머지 학습 설정 유지, 20만 스텝 최종 정책. 교통 seed1001~1005 × 22경로 =110회.

|조건|완주|충돌|시간 초과|
|---|---:|---:|---:|
|R0 seed22|48/110 (43.6%)|59/110 (53.6%)|3/110 (2.7%)|
|H-LR seed22|28/110 (25.5%)|17/110 (15.5%)|65/110 (59.1%)|

원인 분류는이번 최종 평가에 직접 기록된 timeout_diagnostic 기준이며 독립 재현 완료로 표시하지 않는다: {'route_lane_blocked': 65}. seed33 반복은 진행 중이므로 3-seed 결론은 보류한다.

|경로|기본 완주/충돌/시간초과|학습률 변경 완주/충돌/시간초과|
|---|---|---|
|east_through|5 / 0 / 0|2 / 1 / 2|
|east_to_north|1 / 4 / 0|5 / 0 / 0|
|east_to_south|1 / 4 / 0|5 / 0 / 0|
|north_through|5 / 0 / 0|2 / 2 / 1|
|north_to_east|1 / 4 / 0|0 / 1 / 4|
|north_to_local|2 / 3 / 0|0 / 1 / 4|
|north_to_west|2 / 3 / 0|0 / 1 / 4|
|outer_to_south|0 / 2 / 3|5 / 0 / 0|
|sano_east_to_south|4 / 1 / 0|0 / 1 / 4|
|sano_north_through|0 / 5 / 0|0 / 0 / 5|
|sano_north_to_west|3 / 2 / 0|0 / 1 / 4|
|sano_south_through|5 / 0 / 0|4 / 0 / 1|
|sano_south_to_east|0 / 5 / 0|0 / 0 / 5|
|sano_south_to_west|3 / 2 / 0|0 / 1 / 4|
|sano_west_to_north|0 / 5 / 0|0 / 3 / 2|
|sano_west_to_south|2 / 3 / 0|0 / 3 / 2|
|south_through|5 / 0 / 0|4 / 1 / 0|
|south_to_east|0 / 5 / 0|0 / 0 / 5|
|south_to_local|0 / 5 / 0|0 / 0 / 5|
|south_to_west|0 / 5 / 0|0 / 0 / 5|
|west_through|5 / 0 / 0|1 / 0 / 4|
|west_to_local|4 / 1 / 0|0 / 1 / 4|

실행 경로 `results/ic_campaign_v2/runs/H-LR-22-200000`. 코드 커밋 `182a35787919a26382852a63a2d3a103ae99e1dd`. 설정 `complete.json`, 원본 `eval-200000.json`.


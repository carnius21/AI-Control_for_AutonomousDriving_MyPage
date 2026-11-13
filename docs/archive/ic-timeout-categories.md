> **과거 기록** — 작성 당시의 설계·맵·결과입니다. 현재 적용 기준은 [최신 문서 목록](../README.md)을 확인하세요.

# 시간 초과 원인 분류

시간 초과를 곧바로 교통 정체로 해석하지 않는다. 마지막 약 60초를 1초 간격으로 관측하고 아래 증거에 따라 분류한다. 900초 제한과 정책·트래픽·보상은 변경하지 않는다.

|분류|관측 기준|해석 한계|
|---|---|---|
|route_lane_blocked|80% 이상에서 다음 경로로 연결되지 않는 차로, 차로 끝 10m 이내, 속도 0.5m/s 미만|길을 잘못 들어 이미 이탈했다는 뜻이 아니라 필요한 차로를 놓쳐 진행할 수 없는 상태. 정체와 중복되면 이 분류 우선|
|queue_with_slow_leader|80% 이상에서 속도 2m/s 미만, 앞차 25m 이내, 앞차도 2m/s 미만|앞차에 막힌 정황. 도로 전체 병목의 원인까지 확정하지 않음|
|moving_at_timeout|80% 이상에서 속도 2m/s 이상|종료 직전 계속 주행 중. 제한시간 연장 시 완주한다고 보장하지 않음|
|mixed_or_unexplained|어느 기준도 충족하지 않음|혼합 원인·정책 자체 정지·기타 가능성. 추가 검토 필요|
|replay_mismatch|원래 시간 초과 및 종료시간이 재현되지 않음|원본 결과의 원인으로 사용하지 않음|

원본 평가를 보존하고 `results/ic_campaign_v2/timeout-diagnostics/<run>.json`에 경로·seed·원인·마지막 위치·속도·앞차 간격·목표 연결 차로·최근 60개 관측을 별도 저장한다. 정책과 평가 파일 SHA256도 기록한다. `python -m utils.ic_timeout_audit`로 완료된 20만 스텝 정책의 시간 초과만 재현하며, 이미 처리한 사례는 건너뛴다. 실행 도중 새로 완료된 run은 다음 실행에서 처리한다.

새로 시작한 평가 프로세스는 `timeout_diagnostic`을 직접 기록한다. 이미 실행 중인 학습 프로세스는 이전 코드를 사용하므로 중단하지 않고 위 재현 작업으로 보완한다. 기존에 재현한 R0 seed11의 20건은 모두 차로 끝 정지였지만 다른 모델에 이 결론을 일반화하지 않는다. 경로별 분모와 원인별 건수는 진단 완료 후 집계한다.

## 2026-11-07 15:14 KST 실행 중단 복구

상태 파일은 실행 중이었지만 Python/SUMO 프로세스가 모두 존재하지 않는 것을 두 번 확인했다. 기존 오류 로그는 비어 있어 종료 원인은 확정할 수 없다. 정책과 완료된 평가 파일은 보존됐으며, 세 작업(campaign, combination_trials, timeout_audit)을 재개했다. 학습 완료 정책을 재사용하고 저장된 평가 및 진단 사례를 건너뛴다. 종료 당시 진행 중이던 미저장 평가 묶음은 다시 실행한다.

재개 로그: `results/ic_campaign_v2/{campaign,combination,timeout-audit}-resume-20261107-1514.{stdout,stderr}.log`. 재개 코드 기준 `029e3fd`(시간 초과 계측 추가)이며 이전 평가와 관측·보상·행동 정의는 동일하다. 재개 후 평가는 시간 초과 진단 필드가 추가된다. 코드 변경 없는 실행 복구이므로 별도 코드 수정은 하지 않았다.

## BLOCK seed11 진단 완료 (2026-11-07)

시간 초과 45건 모두 원래 종료시간과 시간 초과 결과가 재현됐다. 마지막 약 60초 기준 차로 연결 실패 후 차로 끝 정지 41건, 혼합·미확인 4건이다. 앞차 정체 또는 계속 주행으로 단독 분류된 사례는 0건이다. 이는 기준을 충족한 분류이며 정체가 전혀 없었다는 뜻은 아니다.

|경로|차로 연결 실패 정지|혼합·미확인|
|---|---:|---:|
|north_through|2|0|
|north_to_east|5|0|
|north_to_local|2|0|
|north_to_west|5|0|
|sano_north_to_west|4|0|
|sano_south_to_east|5|0|
|sano_south_to_west|4|0|
|sano_west_to_north|0|2|
|sano_west_to_south|0|2|
|south_to_east|5|0|
|south_to_local|4|0|
|south_to_west|5|0|

실행/증거: `results/ic_campaign_v2/timeout-diagnostics/BLOCK-11-200000.json`. 학습 seed11, 평가 seed1001~1005. 진단 코드 `029e3fd`. 정책 SHA256: `95f5b85151a62301fe3114e427802b91cfdaa220af2606b4cfd6563ccc01415f`. 원본 평가는 유지한다. 나머지 모델 진단은 진행 중이다.

## COMBO seed11 진단 완료 (2026-11-07)

시간 초과 26건 모두 원래 종료시간과 결과가 재현됐으며 26건 모두 마지막 약 60초 기준 경로 연결 차로를 놓쳐 차로 끝에 정지한 것으로 분류됐다. 앞차 정체/주행 중 시간 소진/혼합 분류는 0건이다. 이전 구간의 정체나 차선 변경 기회 부족이 차로 선택 실패에 기여했는지는 이 종료 직전 분류만으로 확정할 수 없다.

|경로|차로 연결 실패 정지|
|---|---:|
|north_to_local|2|
|sano_north_through|1|
|sano_west_to_north|4|
|sano_west_to_south|4|
|south_to_east|5|
|south_to_local|5|
|west_to_local|5|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `78f27d67b982144bc0b1071e44d2e325c84cc37be69536bb055f0bd2ba3c0bec`. 원본 평가 결과는 보존했다.

## COMBO seed22 진단 완료 (2026-11-07)

{'route_lane_blocked': 34}

시간 초과 34건 모두 원래 종료시간과 결과 재현 확인. 종료 직전 기준 분류이며 그 이전 정체의 기여 여부를 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 1}|
|north_through|{'route_lane_blocked': 1}|
|north_to_east|{'route_lane_blocked': 4}|
|north_to_local|{'route_lane_blocked': 4}|
|north_to_west|{'route_lane_blocked': 2}|
|sano_north_to_west|{'route_lane_blocked': 4}|
|sano_south_through|{'route_lane_blocked': 1}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 2}|
|south_to_local|{'route_lane_blocked': 2}|
|south_to_west|{'route_lane_blocked': 2}|

평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO-22-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `100b7aca62795bff4ba903ac99a1e5d66bc4843925432c9abb652d7012241668`.

## COMBO seed33 진단 완료 (2026-11-07)

시간 초과 40건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'route_lane_blocked': 40}. 종료 직전 상태의 분류이며 앞선 정체의 기여는 별도 분석이 필요하다.

|경로|분류별 건수|
|---|---|
|north_to_east|{'route_lane_blocked': 4}|
|north_to_local|{'route_lane_blocked': 3}|
|north_to_west|{'route_lane_blocked': 4}|
|sano_east_to_south|{'route_lane_blocked': 4}|
|sano_north_to_west|{'route_lane_blocked': 4}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|south_to_east|{'route_lane_blocked': 3}|
|south_to_local|{'route_lane_blocked': 3}|
|south_to_west|{'route_lane_blocked': 3}|
|west_to_local|{'route_lane_blocked': 2}|

학습 seed33, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO-33-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `d23e6e83a01a4937885519c284d963cf3e58db6e5aa017c32afa8d55a551da8a`.

## COMBO025 seed11 진단 완료 (2026-11-07)

시간 초과 39건 모두 원래 종료시간·결과가 재현됐으며 종료 직전 경로 연결 차로 실패 정지로 분류됐다. 학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-11-200000.json`, 진단 코드 `029e3fd`. 정책 SHA256 `49a5b897fa11ac0ac2992ab2c0a507548b130fbcb2cb5b061f8bba3c26d4ba24`.

## COMBO025 seed22 진단 완료 (2026-11-07)

시간 초과 55건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'route_lane_blocked': 55}. 종료 직전 상태 분류이며 이전 정체의 기여는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_through|{'route_lane_blocked': 2}|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_west|{'route_lane_blocked': 5}|
|sano_north_through|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 1}|
|sano_south_through|{'route_lane_blocked': 1}|
|sano_south_to_west|{'route_lane_blocked': 4}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|
|west_through|{'route_lane_blocked': 4}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed22, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-22-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `5bf1b2a082fa7540bc2d3417a6db0ea78838ded5812b0db048b293e5b8d292e0`.

## COMBO025-NO-RAMP-11-200000 진단 완료 (2026-11-07)

시간 초과 61건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'route_lane_blocked': 61}. 종료 직전 상태 분류이며 이전 정체의 기여는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_local|{'route_lane_blocked': 4}|
|north_to_west|{'route_lane_blocked': 5}|
|sano_east_to_south|{'route_lane_blocked': 5}|
|sano_north_through|{'route_lane_blocked': 3}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 5}|
|sano_west_to_south|{'route_lane_blocked': 5}|
|south_to_east|{'route_lane_blocked': 3}|
|south_to_local|{'route_lane_blocked': 3}|
|south_to_west|{'route_lane_blocked': 3}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-NO-RAMP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `76bc7f1aeb1aea775e1fdbf0dee6c232a7f8c132b751a60381e48a86447468bc`.

## COMBO025-NO-ROUTE100-11-200000 진단 완료 (2026-11-07)

시간 초과 51건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'route_lane_blocked': 51}. 종료 직전 상태 분류이며 이전 정체의 기여는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 1}|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_local|{'route_lane_blocked': 1}|
|north_to_west|{'route_lane_blocked': 5}|
|sano_east_to_south|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 4}|
|sano_west_to_north|{'route_lane_blocked': 4}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 4}|
|south_to_west|{'route_lane_blocked': 5}|
|west_through|{'route_lane_blocked': 2}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-NO-ROUTE100-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `4e6a0f26cb3ac1b16b49df3e47a978dcc5676059b247bdf95ed76308b2c051ea`.

## COMBO025-NO-ZIP-11-200000 진단 완료 (2026-11-07)

시간 초과 52건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'route_lane_blocked': 52}. 종료 직전 상태 분류이며 이전 정체의 기여는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_local|{'route_lane_blocked': 5}|
|north_to_west|{'route_lane_blocked': 4}|
|sano_east_to_south|{'route_lane_blocked': 2}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-NO-ZIP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `9e410eed39d7eefccfb8b83662d48426ae336d38b02c83019cf26e79db8b6200`.

## GAP-11-200000 진단 완료 (2026-11-07)

시간 초과 25건 모두 원래 종료시간 및 결과가 재현됐다. 분류: {'mixed_or_unexplained': 14, 'route_lane_blocked': 11}. 종료 직전 상태 분류이며 이전 정체의 기여는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_to_east|{'mixed_or_unexplained': 1}|
|north_to_west|{'mixed_or_unexplained': 1}|
|sano_north_to_west|{'mixed_or_unexplained': 1}|
|sano_south_to_west|{'mixed_or_unexplained': 4}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'mixed_or_unexplained': 2}|
|south_to_local|{'mixed_or_unexplained': 2}|
|south_to_west|{'mixed_or_unexplained': 3}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/GAP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `82ef9577a6560ed34b02d1f7bc8907826ef8c24cda86f1caa9a7ba8fb8085a7e`.

## PREP-11-200000 진단 완료 (2026-11-07)

시간 초과 58건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 58}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_through|{'route_lane_blocked': 1}|
|north_to_east|{'route_lane_blocked': 2}|
|north_to_west|{'route_lane_blocked': 3}|
|sano_north_through|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_through|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|
|west_through|{'route_lane_blocked': 4}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed는 run 이름 참조, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/PREP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `470d2f0f1a3413309d95fc2cc1d60ef0e7c32fb2ff8efef847f8477a3e41037a`.


## R0-11-200000 진단 완료 (2026-11-07)

시간 초과 20건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 20}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_to_west|{'route_lane_blocked': 2}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_through|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 2}|
|south_to_local|{'route_lane_blocked': 2}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed는 run 이름 참조, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/R0-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `b0811919876f05b845d4422bf2afa45a10def53c44be6aea062b8145fb4e2ec2`.


## R0-22-200000 진단 완료 (2026-11-07)

시간 초과 3건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 3}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|outer_to_south|{'route_lane_blocked': 3}|

학습 seed는 run 이름 참조, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/R0-22-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `58c788444ac0b231ac20145d8d669e4a824f1e36aff4aa5109f4f2df2f727283`.

## R0-33-200000 진단 완료 (2026-11-07)

시간 초과 15건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 15}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_to_east|{'route_lane_blocked': 1}|
|north_to_local|{'route_lane_blocked': 3}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed33, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/R0-33-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `887dcc4cc9d1a086907520f725909ba2336bd04ec1115e438f35b4e0bd834771`.

## RAMP-11-200000 진단 완료 (2026-11-07)

시간 초과 42건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 42}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_through|{'route_lane_blocked': 1}|
|sano_east_to_south|{'route_lane_blocked': 4}|
|sano_north_through|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_through|{'route_lane_blocked': 1}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 1}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 1}|
|south_to_local|{'route_lane_blocked': 1}|
|south_to_west|{'route_lane_blocked': 2}|
|west_through|{'route_lane_blocked': 4}|
|west_to_local|{'route_lane_blocked': 4}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/RAMP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `7fca92c1f62626bae8e10cd8d6baa9fd05dcf7d52960c4b7f3340770c321df4d`.

## ROUTE100-11-200000 진단 완료 (2026-11-07)

시간 초과 44건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 44}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_to_east|{'route_lane_blocked': 4}|
|north_to_local|{'route_lane_blocked': 3}|
|north_to_west|{'route_lane_blocked': 4}|
|sano_east_to_south|{'route_lane_blocked': 3}|
|sano_north_through|{'route_lane_blocked': 4}|
|sano_north_to_west|{'route_lane_blocked': 2}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 3}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 2}|
|south_to_local|{'route_lane_blocked': 2}|
|south_to_west|{'route_lane_blocked': 2}|
|west_to_local|{'route_lane_blocked': 2}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/ROUTE100-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `f798d678d09bfe708c5bc14cf9d079cdf3c3cebe22573060371f03bdddb3ecba`.

## ZIP-11-200000 진단 완료 (2026-11-07)

시간 초과 61건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 61}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_through|{'route_lane_blocked': 3}|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_local|{'route_lane_blocked': 5}|
|north_to_west|{'route_lane_blocked': 1}|
|sano_north_through|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 4}|
|sano_south_through|{'route_lane_blocked': 1}|
|sano_south_to_west|{'route_lane_blocked': 4}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|
|west_through|{'route_lane_blocked': 5}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/ZIP-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `15c48aa672f652384965c3382ff0d6e81497d263d2708b85adc99adbe09665c3`.

## COMBO025-33-200000 진단 완료 (2026-11-07)

시간 초과 58건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 58}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|north_through|{'route_lane_blocked': 1}|
|north_to_east|{'route_lane_blocked': 3}|
|north_to_local|{'route_lane_blocked': 4}|
|north_to_west|{'route_lane_blocked': 3}|
|sano_east_to_south|{'route_lane_blocked': 5}|
|sano_north_through|{'route_lane_blocked': 4}|
|sano_north_to_west|{'route_lane_blocked': 4}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 2}|
|sano_west_to_south|{'route_lane_blocked': 2}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed33, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/COMBO025-33-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `ea9f60fa1b2e6882fdc2619a9cc4ecf000dcc8eda7c83937c53e15827e0e1063`.

## H-LR-11-200000 진단 완료 (2026-11-07)

시간 초과 79건 모두 원래 종료시간·결과가 재현됐다. 종료 직전 기준 분류: {'route_lane_blocked': 79}. 이전 정체의 기여 여부는 확정하지 않는다.

|경로|분류별 건수|
|---|---|
|east_through|{'route_lane_blocked': 2}|
|north_through|{'route_lane_blocked': 3}|
|north_to_east|{'route_lane_blocked': 5}|
|north_to_west|{'route_lane_blocked': 5}|
|sano_east_to_south|{'route_lane_blocked': 5}|
|sano_north_through|{'route_lane_blocked': 5}|
|sano_north_to_west|{'route_lane_blocked': 5}|
|sano_south_through|{'route_lane_blocked': 5}|
|sano_south_to_east|{'route_lane_blocked': 5}|
|sano_south_to_west|{'route_lane_blocked': 5}|
|sano_west_to_north|{'route_lane_blocked': 3}|
|sano_west_to_south|{'route_lane_blocked': 3}|
|south_through|{'route_lane_blocked': 3}|
|south_to_east|{'route_lane_blocked': 5}|
|south_to_local|{'route_lane_blocked': 5}|
|south_to_west|{'route_lane_blocked': 5}|
|west_through|{'route_lane_blocked': 5}|
|west_to_local|{'route_lane_blocked': 5}|

학습 seed11, 평가 seed1001~1005. 증거 `results/ic_campaign_v2/timeout-diagnostics/H-LR-11-200000.json`. 진단 코드 `029e3fd`. 정책 SHA256 `e1b5c49e4bf32c8e13a47f466af9b55c6f60734b36b0cf24cb50f48dc0f37535`.

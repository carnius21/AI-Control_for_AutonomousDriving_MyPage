# 퇴계원IC 버스(HV)·AV 통합 — 2026-11-02

기존 도로 형상, 12개 Route, 교통량 단계와 분홍/초록 승용차 테스트를 유지하면서 버스 혼입과 AV 한 대를 선택적으로 추가했습니다. 기본 `python toegyewon.py gui`는 이전처럼 승용차만 실행합니다. 버스는 기존 배경 수요의 일부를 교체하며, AV는 별도로 한 대 추가합니다.

**검증된 AV 완주는 SUMO 기본 모델 결과입니다. 학습된 PPO 성능을 의미하지 않습니다.** 저장소에서 기존 `.pt`/`.pth` 체크포인트가 발견되지 않았습니다. PPO 로딩·추론·TraCI 연결과 차원 오류 검사는 구현·검증했지만 학습 모델의 주행 성능은 미검증입니다. PPO 재학습과 Offline RL 학습은 수행하지 않았습니다.

## Windows CMD 실행

저장소 루트에서 기존 가상환경을 사용합니다.

```bat
python toegyewon.py gui
python toegyewon.py gui --bus-ratio 0.1
python toegyewon.py gui --av sumo
python toegyewon.py gui --bus-ratio 0.1 --av sumo

REM 분홍 Route: 북쪽 진입 → 동쪽 램프 출구 (AV 기본값, 90초 출발)
python toegyewon.py gui --bus-ratio 0.1 --av sumo --av-route pink --av-depart 90

REM 초록 Route: 남쪽 진입 → 서쪽 출구 (급감속이 관찰된 상호작용 조건)
python toegyewon.py gui --bus-ratio 0.1 --av sumo --av-route green --av-depart 103

REM 동일 조건 headless 실행 및 상세 AV 로그
python toegyewon.py run --bus-ratio 0.1 --av sumo

REM 독립 검증: 버스 먼저, AV 다음
python toegyewon.py validate-bus --output scenarios/toegyewon/build/bus_final
python toegyewon.py validate-av --output scenarios/toegyewon/build/av_final
python toegyewon.py validate
python -m unittest scenarios.toegyewon.test_traffic scenarios.toegyewon.test_av -v
```

`--traffic low|medium|high`, `--weave-factor`, `--demand-scale`, `--seed`, `--config`, `--output`도 그대로 사용할 수 있습니다. `--demand-scale 0`은 배경 수요를 끄지만 기존 분홍/초록 테스트 차량과 활성화한 AV는 남깁니다. 순수 AV 단독 조건은 `validate-av`가 별도 생성합니다.

SUMO-GUI는 `--start false --quit-on-end false`로 수동 Play와 종료 후 창 유지 설정을 명시합니다. 기본 SUMO AV는 독립 GUI에서 실행하고, GUI 로그(`gui.fcd.xml`, `gui.trips.xml`, `gui.lanechanges.xml`)는 창을 닫아야 완전히 마감됩니다. 향후 PPO GUI는 TraCI 연결을 유지한 상태에서 종료 화면을 확인하고 **CMD에서 Enter를 눌러 연결·로그를 마감**합니다. `--checkpoint`가 없으면 PPO GUI는 열지 않고 설명과 함께 실패합니다.

GUI 프로세스 실행 중 종료 XML을 너무 일찍 읽는 문제를 발견해, 독립 SUMO GUI와 PPO GUI의 수명 관리를 분리하고 TraCI 출력 마감을 기다리도록 수정했습니다. Windows 화면 자동화 도구는 `failed to start Node runtime ... os error 3`으로 초기화에 실패했습니다. 따라서 **최종 GUI 화면의 수동 Play·창 유지·색상 렌더링은 직접 검증하지 못했습니다.** 아래 수치는 모두 headless SUMO/TraCI 실측입니다.

## A. 버스

### 차량 가정과 통행 권한

| 항목 | BUS 값 | 의미 |
|---|---:|---|
| vClass / guiShape | bus / bus | 실제 버스 통행 클래스와 GUI 외형 |
| 색상 | 주황 `(1, 0.65, 0)` | 회색 HV, 분홍/초록 테스트, 빨간 AV와 구분 |
| 길이 / 폭 | 12m / 2.5m | 일반 대형 버스를 가정 |
| 가속 / 정상 감속 | 1.2 / 3.0m/s² | 기존 HV의 2.6 / 4.5보다 완만 |
| 비상 감속 | 7.0m/s² | 모델 설정 상한; 편안한 감속을 뜻하지 않음 |
| 최고속도 | 25m/s (90km/h) | edge 제한속도가 더 낮으면 해당 제한 적용 |
| tau / minGap | 1.5초 / 3m | 차량추종 시간 간격·정지 간격 |
| 차량추종 / 차로 변경 | Krauss / LC2013 | 기본 SUMO 제어 |
| lcStrategic / lcCooperative / lcSpeedGain / lcKeepRight | 모두 1 | 기본 경로 선택·협조·속도 이득·우측 선호 |
| sigma / speedDev | 0 / 0 | 기존 결정적 실험 설정 유지 |

모두 관측으로 보정한 실제 특정 차종 제원이 아닌 **조정 가능한 가정값**입니다. `config.json → buses.vehicle`에서 변경합니다. 차로 변경 시간은 기존 전체 설정 `lane_change_duration=1.0초`를 유지합니다. 강제 이동·버스 속도 명령·버스 차로 변경 명령을 사용하지 않습니다.

도로 생성의 `allow="passenger"`를 `allow="passenger bus"`로 확장했습니다. 승용차 권한과 기존 차로 변경 금지 구간은 유지합니다. 외부/내부 lane XML의 형상·길이·속도·연결은 통행 권한 속성을 제외하고 기존과 동일한지 확인합니다. 버스 `vClass`를 승용차로 위장하지 않습니다.

### 수요와 Route

`buses.ratio`의 기본값은 0입니다. `--bus-ratio 0.1`이면 각 Route 예정 대수의 10%를 버스로 바꿉니다. 각 Route 버스 대수는 `floor(N × ratio + 0.5)`로 정하고 동일한 출발 슬롯에 고르게 배치합니다. 따라서 총수요와 Route별 출발 일정은 유지되지만 실제 전체 비율에는 반올림 차이가 있습니다. 기본 보통 교통의 배경 174대 중 버스가 18대이고, 기존 두 테스트 승용차까지 합하면 176대입니다.

예를 들어 JSON에 다음처럼 설정하면 전체 버스 비율 5%, 분홍·초록 Route만 20%로 지정할 수 있습니다. CLI `--bus-ratio`는 모든 Route에 동일 비율을 적용하며 JSON의 Route별 예외를 초기화합니다.

```json
"buses": {
  "ratio": 0.05,
  "route_ratios": {"pink": 0.2, "green": 0.2},
  "vehicle": {"length": 12, "width": 2.5, "accel": 1.2, "decel": 3}
}
```

버스는 기존 12개 Route 모두에 투입할 수 있고, 6개 weave 통과 Route에도 배치됩니다. 생성 ID는 `bus_pink.9`, `bus_green.9`처럼 경로와 슬롯을 포함합니다. 기존 테스트 차량 `pink`, `green`은 계속 승용차입니다. 비율 0일 때는 기존 flow XML 생성 방식을 그대로 사용합니다.

### 버스 실측

SUMO 1.27.1, Python 3.12.9, seed 21, step 0.2초, 투입 예정 180초, 배경 검증 한도 600초입니다. 버스 검증을 먼저 마친 뒤 AV를 구현했습니다.

| 조건 | 완료 | weave 차로 변경 | 최저 가속도(m/s²) |
|---|---:|---:|---:|
| 버스 분홍 Route 단독 | 1/1 | 2 | −3.00 |
| 버스 초록 Route 단독 | 1/1 | 1 | −3.00 |
| 분홍 버스 + 초록 승용차 동시 접근 | 2/2 | 2(전체) | −6.37 |
| 분홍 승용차 + 초록 버스 동시 접근 | 2/2 | 2(전체) | −5.33 |
| 기존 승용차 교통 | 176/176 | 101 | −5.33 |
| 버스 10% 혼입 | 176/176 | 104 | −5.33 |

모든 조건에서 충돌·Teleport·SUMO 실행 경고는 0입니다. 혼입 조건은 BUS 18/18, HV 158/158 완료입니다. 각 버스의 Route 순서, weave 중심선 교차 기록, 후속 진출 edge 도달과 최종 도착을 검사했습니다. weave에서 승용차가 20m 이내 버스를 앞차로 관측한 양은 **3.2 차량·초**, 그중 −0.5m/s² 미만 감속을 한 양은 **0.2 차량·초**였습니다. 이는 간격 조절의 관측 근거이며 운전자의 양보 의도를 판정한 값은 아닙니다.

전체 차로 변경은 157→159회, 평균 속도는 12.13→11.48m/s, 완료 차량 평균 timeLoss는 4.23→8.21초였습니다. 급제동 에피소드(−4.5m/s² 미만)는 9→5회로 감소했지만 지연은 증가했습니다. 대기열·출발 위상 영향 때문에 단일 지표를 안전성 개선으로 해석하지 않습니다.

## B. 기존 AV 분석과 새 인터페이스

| 구분 | 기존 고속도로 코드의 가정 | 퇴계원IC 구현 |
|---|---|---|
| Simulation | `r0`, `ego_type`, 전역 TraCI, 도로 전체 prefill | 12개 유효 Route, `AV`, 연결별 TraCI, 기존 교통 수요 |
| 도로 | 12km·3차로·33.33m/s, 중앙 출발 | 현재 edge별 차로 수/제한속도, OPEN 간 Route, `departLane=best` |
| Observation | 실제 31차원, 5개 상대 차로, 링크 존재 여부, 첫 연결을 따라 밀도 조회 | 동일한 31 슬롯 형식 + 선택적 12개 경로 특징, 선택 Route를 따라 분기 조회 |
| Action | 가감속 + 좌/유지/우, 60m 이내 차로 변경 보호 | 2차원 규약 유지, 짧은 edge를 막는 60m 규칙 제거, 실제 차체 길이와 Route로 요청 검사 |
| 안전 설정 | `setSpeedMode(0)`, `setLaneChangeMode(0)` | **speedMode=31, laneChangeMode=1621** |
| Reward | 속도, 근접, 충돌, 도착 + 추월 관련 항 | 국소 제한속도 보상·근접·거절 요청·도착/실패 보상; 학습 미실시 |
| Episode | 도착 이벤트/충돌/소멸/스텝 한도 | 삽입 대기, 실제 Route 순서·목적지 도착, 충돌/Teleport/이탈/소멸/시간 한도 구분 |
| Policy | `algorithms.ppo.PPO`, Gaussian/Hybrid 네트워크, `predict` | **같은 PPO 클래스·네트워크·predict를 재사용**, 별도 엄격한 로더 |

기존 `_lane_connectivity`는 “어느 방향으로든 링크가 있음”을 연결 가능으로 취급하고, `_lane_density`는 첫 링크를 사용합니다. 분기망에서는 목적지와 다른 링크일 수 있습니다. 또한 기존 차로 변경 보호의 `lanePosition < 60m` 조건은 30m weave 전체를 차로 변경 금지처럼 처리할 수 있어 가져오지 않았습니다. 기존 도착 판정은 이미 SUMO arrived 이벤트를 사용하므로 이 개념은 유지하고, 목적 Route 순서를 추가 확인합니다.

`env/`, `train.py`, `test.py`, `algorithms/`, `utils/`는 수정하지 않았습니다. 기존 고속도로 클래스를 통째로 복사하거나 상속해 숨겨진 전역 의존성을 끌어오지 않았습니다. PPO 및 기존 평가 유틸이 받는 `reset/step`, `predict`, `info` 규약을 유지하는 별도 `ToegyewonEnv`를 구성했습니다.

### Observation

기본 `--observation route`는 **43차원 float32, [-1,1]**입니다. `--observation legacy`는 앞의 **31차원**만 반환합니다.

| 인덱스 | 정의 |
|---|---|
| 0 | 속도 / 33.33 |
| 1–20 | 좌2·좌1·현재·우1·우2 각각 앞/뒤 gap 및 상대속도 (4개씩) |
| 21–25 | 각 차로의 물리적 연결성, 없는 차로는 −1 |
| 26–30 | 각 차로의 근사 전방 밀도, 없는 차로는 1 |
| 31–35 | 각 차로가 **Route의 다음 edge**에 연결되는지: 없음 −1 / 불가 0 / 가능 1 |
| 36 | 현재 lane 끝까지 거리 / 관측거리 |
| 37 | SUMO bestLanes의 목표 차로 오프셋 / 4 |
| 38 | 현재 차로 index / 해당 edge의 최대 index |
| 39 | Route 진행 index / 마지막 index |
| 40 | 현재 허용속도 / 33.33 |
| 41 | 내부 junction lane 여부 |
| 42 | SUMO bestLanes가 제공하는 차로 변경 없이 주행 가능한 잔여거리 / 관측거리 |

거리 관측범위는 기본 50m이며 정규화 값은 범위 안으로 clip합니다. 앞 gap은 양수, 뒤 gap은 음수입니다. 옆 차량의 차체가 종방향으로 겹치는 경우 벡터 gap은 0으로 두고 JSON 로그에는 실제 bumper gap과 overlap 여부를 별도로 남깁니다. 버스 길이를 5m 승용차로 간주하지 않습니다.

`info`와 `.av.jsonl`에는 현재 edge/lane/좌표, Route와 다음 edge, 목표 차로, 주행거리, 이웃 ID/type/실제 길이/상대속도, 모드와 제어 요청도 남습니다. 관측은 국소 5개 차로에 제한되며 모든 합류 접근로 차량을 완전히 관측하는 전역 상태가 아닙니다.

31차원은 기존 **배열 형식과 입력 크기**의 호환용입니다. 곡선망, Route를 따르는 밀도 조회, 버스 및 겹침 처리, 0.2초 스텝과 AV 가감속 한계가 기존 고속도로 학습 조건과 다르므로 같은 차원이라고 동일한 관측 분포·정책 성능이 보장되지 않습니다.

### Action·Reward·제어 방식

- `sumo`: AV도 Krauss/LC2013가 주행합니다. 속도/차로 명령은 보내지 않으며 AV 식별·관측·안전 모드·종료 판정만 연결합니다. **RL 결과가 아닙니다.**
- `external`(Gym 인터페이스): action `[accel_raw, lane_raw]`, 각 값 [-1,1]. 첫 값은 AV의 +2.6/−4.5m/s² 한계에 대응하고 `v + accel × dt`를 현재 허용속도 내로 제한합니다. 두 번째 값은 ±0.5 임계로 오른쪽 −1 / 유지 0 / 왼쪽 +1입니다.
- `ppo`: 기존 PPO의 `predict` 출력을 위 external 인터페이스로 전달합니다. 요청 전 금지 edge/권한/차로 존재/목적 Route 이탈 방향/앞뒤 gap/겹침을 검사하고, SUMO 안전 기능도 유지합니다. 0 차로 명령은 차로를 고정하지 않아 SUMO의 목적지 차로 선택을 방해하지 않습니다. 따라서 **PPO 제안 + Route 보호 + SUMO 안전/전략적 변경**의 조합입니다.

제출한 차로 명령 수와 실제 차로 변경 횟수는 구분합니다. 거절 사유와 원시 행동·목표 속도를 로그에 기록합니다. 테스트용 반복 왼쪽 요청은 학습된 규칙이나 Policy로 표현하지 않습니다.

Reward는 실행 인터페이스용 초기 정의입니다: `0.1 × 속도/현재 허용속도`, 앞 gap 6m 미만이면 −0.1, 거절 요청이면 −0.02, 도착 시 +2, 충돌/이탈/소멸/시간 초과 등 실패 시 −5입니다. 향후 퇴계원IC 전용 학습 전에 보상과 제어 주기를 검토해야 합니다. 안전 보장은 Reward가 아니라 SUMO와 요청 검사에 의존하며, 급제동이 없어지는 것을 보장하지 않습니다.

정상 도착은 SUMO arrived 이벤트와 방문한 외부 edge 순서가 기대 Route와 같을 때만 인정합니다. 최초 안전 삽입 지연은 별도 제한으로 대기하고 실패 시 `insertion_timeout`을 보고합니다. Gym episode는 AV 종료 시 끝나며 검증 러너는 나머지 교통도 600초 한도까지 배출해 전체 완료 여부를 확인합니다.

### PPO 연결

학습된 파일이 있는 경우에만 다음처럼 실행합니다. 예시 파일은 저장소에 포함돼 있지 않습니다.

```bat
REM 기존 31입력 PPO: 명시적으로 legacy 선택, 당시 activation도 맞출 것
python toegyewon.py run --av ppo --observation legacy --checkpoint results\your_run\model.pt --policy-activation relu

REM 향후 퇴계원IC 43입력 모델
python toegyewon.py run --av ppo --observation route --checkpoint results\toegyewon\model.pt
```

`torch.load(weights_only=True)`로 읽고 입력 차원, Hybrid의 1+3 head 또는 Gaussian의 2-action head, hidden layer 크기, 전체 state_dict를 검사합니다. 31입력을 43입력에 자동 padding하거나 새 특징을 몰래 버리지 않습니다. bare state_dict에는 activation·관측 의미가 없으므로 당시 설정을 맞춰야 합니다. 새 메타데이터 wrapper는 `algorithm="ppo"`, `observation_schema="toegyewon-route43-v1"`, `activation`, `state_dict`를 저장하도록 지원합니다. 학습 스크립트는 변경하지 않았습니다.

검증에서는 임시 초기화 네트워크로 31/43 입력 로딩과 각각 5개 SUMO step의 추론→TraCI 전달만 확인했습니다. 모델을 훈련하거나 이 모델의 완주·안전 성능을 평가한 것은 아닙니다. 체크포인트 없음·입력 차원 불일치·출력 차원 오류·schema 불일치는 명시적으로 실패합니다.

## C. AV 실측과 30m 구간의 한계

다음은 모두 SUMO 기본 제어입니다. 단독 조건은 출발 0초, HV 조건은 분홍 0초/초록 17.4초, 혼합 조건은 분홍 90초/초록 103초 출발입니다. 동시 접근 조건은 각 차량의 단독 weave 진입 시간을 측정해 출발 시각만 조정했습니다.

| 조건 | AV Route | 전체 완료 | AV weave 변경 | AV 최저 가속도(m/s²) | weave 버스 근접 관측(초) |
|---|---|---:|---:|---:|---:|
| 단독 | pink | 1/1 | 2 | −4.50 | 0 |
| 단독 | green | 1/1 | 1 | −4.50 | 0 |
| HV 배경 | pink | 177/177 | 2 | −4.50 | 0 |
| HV 배경 | green | 177/177 | 1 | −4.50 | 0 |
| **HV+버스 10%, 기본 AV 예시** | **pink** | **177/177** | **3** | **−3.76** | **1.2** |
| HV+버스 10%, 동시 진입 근접 조건 | green | 177/177 | 1 | **−8.16** | 22.6 |
| 분홍 버스와 동시 접근 | green | 2/2 | 1 | **−6.37** | 21.0 |
| 초록 버스와 동시 접근 | pink | 2/2 | 1 | **−5.33** | 11.2 |

모든 경우 AV 목적지 도착, 전체 차량 배출, 충돌·Teleport·SUMO 실행 경고 0을 확인했습니다. pink는 `N_in → … → E_ramp_out`, green은 `S_in → … → W_out`입니다. 혼합 조건의 구성은 **HV 158 + BUS 18 + AV 1**입니다. 버스 근접은 weave에서 관측된 주변 차량의 gap이 20m 이내인 시간이며, 항상 같은 차로 앞차였다는 뜻은 아닙니다. 별도의 같은 차로 버스 앞차 시간도 결과 JSON에 있습니다.

별도 **안전 요청 검사**에서는 AV에 매 스텝 `[1, 1]`(가속·왼쪽)을 제안했습니다. 2/2 도착, 실제 weave 변경 1회, 충돌·Teleport 0이었고, 안전 gap 부족 **15회**, 목표 차로 없음 **374회**, junction/변경 금지 **54회**를 거절했습니다. 이것은 적대적 요청에 대한 검사이며 PPO 성능 결과가 아닙니다.

**충돌 없이 완주했다고 편안하거나 현실적인 차로 변경이 검증된 것은 아닙니다.** 초록 AV 103초 출발 조건에서는 144.0초의 `weave_2`에서 −8.16m/s² 감속이 기록됐습니다. 당시 인접 차로의 12m `bus_pink.9` 차체와 종방향 위치가 겹치고, AV는 차로 3으로 이동해야 하는 상태였습니다. 이는 같은 차로 충돌을 의미하지 않지만, 짧은 필수 차로 교환 구간에서 시간·공간 여유가 크게 줄어드는 한계 사례입니다. 이 결과를 숨기거나 도로를 임의로 늘리지 않았습니다.

기본 AV 예시는 관측된 급제동을 피하면서 버스 근접을 볼 수 있는 pink/90초로 정했습니다. 별도 출발 위상에서는 다시 급감속이 나타날 수 있습니다. 정확한 현장 제원·운전자 행태·버스 후륜 궤적 자료가 없으므로 현실성은 확정할 수 없습니다. LC2013의 차로 교환과 직사각형 차체 모델은 대형 버스의 조향 한계·후륜 안쪽 궤적·승객 승차감을 검증하는 차량 동역학 모델이 아닙니다.

`failures`는 완주/충돌/Teleport/경로/필수 변경 회귀 실패를 뜻합니다. 급제동은 통과 결과에서도 `safety_findings`에 별도로 기록하므로, `failures=[]`를 실도로 안전성 인증으로 읽으면 안 됩니다.

## 파일·로그·남은 작업

| 파일 | 역할 |
|---|---|
| `scenarios/toegyewon/vehicles.py` | HV/BUS/AV vType과 일정 보존 버스 교체 |
| `config.json` | 버스 제원/비율, AV Route·출발·관측·안전 요청 설정 |
| `network.py` | 버스 통행 권한, 선택적 AV 및 혼합 수요 생성 |
| `av_observation.py` | 31/43 관측, 목적 Route 특징, 안전한 행동 요청 |
| `av_env.py` | Gym reset/step, TraCI 연결, AV 상태·종료·로그·교통 배출 |
| `policy.py` | 기존 PPO 추론 로더와 실행 러너; 학습 없음 |
| `validate.py` | 차종별 도착과 버스/승용차 상호작용 지표 확장 |
| `validate_bus.py` | 버스 단독·동시 접근·동일 수요 혼입 비교 |
| `validate_av.py` | AV 단독/HV/혼합/버스 근접/안전 요청 검사 |
| `test_av.py` | 수요 일정/대수 보존, 비율, PPO 차원·schema 회귀 테스트 |
| `toegyewon.py` | 기존 명령 보존, 버스/AV 옵션 및 별도 검증 명령 |

[버스 결과](bus_validation.json), [AV 결과](av_validation.json), [구조·기존 교통·PPO 연결 검사](bus_av_checks.json)를 검토할 수 있습니다. 문서의 결과 JSON은 핵심 지표와 버스/AV 기록을 보존한 요약이며, 전체 궤적은 다음 로컬 생성 폴더에 있습니다.

- `build/bus_final/`: `.trajectory.csv`, `.lanechanges.xml`, `.trips.xml`, `.collisions.xml`, `.result.json`.
- `build/av_final/`: `.av.jsonl`(관측·상태·요청·거절·종료), `.lanechanges.xml`, `.trips.xml`, `.collisions.xml`, `.result.json`.
- `build/default_final/`: 기본 혼합 AV 실행의 전체 결과.

수정 전 승용차 기본값과의 궤적/변경 기록 동등성, source OSM 해시, 네트워크 기하/연결 보존을 검사했습니다. 회귀 테스트 11개가 통과했습니다. 모든 생성물은 Python 생성기를 통해 만들었으며 build XML을 직접 수정하지 않았습니다. `ljj`에서 작업했고 Commit/Push는 수행하지 않았습니다.

남은 작업은 실제 학습 체크포인트 평가, 여러 수요·seed·출발 위상에서의 반복 평가, 현장 기반 버스/차로 변경 보정, 장시간 고밀도 혼합 교통 검증, 퇴계원IC 전용 43차원 Policy 학습 및 보상 검토입니다. 현재 실측은 결정적 승용차/버스 모델과 seed 21의 유한 시나리오입니다. GUI 최종 화면 검사는 위 런타임 장애로 미완료입니다.

차종 설정은 [SUMO 차량 유형](https://sumo.dlr.de/userdoc/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html), 안전 모드는 [TraCI 차량 제어](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html), Route 차로 정보는 [Vehicle Value Retrieval](https://sumo.dlr.de/docs/TraCI/Vehicle_Value_Retrieval.html)를 참고했습니다. [차로 변경 출력](https://sumo.dlr.de/docs/Simulation/Output/Lanechange.html)의 change는 차량 중심의 차로 경계 교차 기록이며, 버스 차체 전체의 조향 궤적 검증과는 구분합니다.

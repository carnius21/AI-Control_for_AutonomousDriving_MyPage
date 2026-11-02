# 퇴계원IC 교통량과 상호작용 — 2026-11-02

기본값은 **보통(`medium`), weave 가중치 2**입니다. 기존 74대에서 176대로 증가하고, 공유 구간의 차로 변경이 32회에서 101회로 늘었습니다. 도로 형상·차로 연결·Krauss/LC2013 설정·분홍/초록 테스트 차량은 유지했습니다. 관측 교통량을 보정한 모델은 아니며, 높음 단계는 정체를 관찰하는 실험 조건입니다.

## 실행과 설정

저장소 루트의 기존 Python/SUMO 환경에서 실행합니다.

```powershell
python toegyewon.py gui                         # 보통 + weave 집중 (기본값)
python toegyewon.py gui --traffic low
python toegyewon.py gui --traffic high
python toegyewon.py gui --traffic medium --weave-factor 1  # 집중 해제
python toegyewon.py gui --traffic low --weave-factor 1     # 이전 수요 재현
python toegyewon.py gui --traffic high --demand-scale 1.2

python toegyewon.py validate                    # 단독/두 차량/12 Route/현재 배경 수요
python toegyewon.py compare                     # 이전/낮음/보통 균등/보통/높음 비교
python -m unittest scenarios.toegyewon.test_traffic -v
```

`--config`, `--output`, `--seed`도 지원합니다. `compare`는 `--traffic` 선택과 관계없이 모든 단계를 비교합니다. `--weave-factor`와 `--demand-scale`은 이전 기준을 제외한 비교 조건에 적용됩니다. `medium_uniform`은 weave 배수만 1로 돌리므로, 사용자가 수정한 Route 가중치는 그대로 적용됩니다.

`config.json`의 `traffic` 설정:

| 설정 | 의미 |
|---|---|
| `profile` | `low` / `medium` / `high` |
| `profiles.*.period` | 균등 배분 시 Route별 기본 간격: 30 / 12 / 6초 |
| `scale` | 전체 배경 수요 배수. 0이면 배경 없이 기존 두 색상 차량만 생성 |
| `route_weights` | Route별 상대 생성 빈도. 2이면 가중치 1인 동등 그룹 Route의 두 배, 0이면 해당 배경 Route 제외 |
| `weave_factor` | weave 통과 6개 Route에 곱하는 추가 가중치. 1이면 집중 해제, 2이면 기본 집중 |
| `end` | 예정 출발 시간의 상한(기본 180초). 안전한 삽입을 기다리는 차량은 이후에도 실제 출발 가능 |

총 배경 수요율은 `12 × 3600 / period × scale` 대/시입니다. Route별 수요율은 이 값에 **유효 가중치 / 모든 유효 가중치의 합**을 곱합니다. 따라서 가중치는 전체 수요율을 유지하며 비율을 바꾸고, `scale`은 전체 수요율을 바꿉니다. 특정 Route의 가중치를 0으로 하면 그 수요는 다른 Route로 재분배됩니다. 모든 가중치를 0으로 두려면 `scale`도 0이어야 합니다. 두 테스트 차량은 별도로 유지됩니다.

예를 들어 기본 보통 단계는 총 3,600대/시 중 weave Route 각각 400대/시(9초 간격), 나머지 각각 200대/시(18초 간격)입니다. 모든 Route 가중치가 1일 때 weave 비중은 배수 1에서 50%, 배수 2에서 66.7%입니다. `pink`, `N_E_main`, `green`의 `route_weights`를 올리면 차로 교환이 필요한 경로에 더 집중할 수 있습니다.

원래 Route 순서별 `0, 2, …, 22초` 시작 위상을 유지합니다. 예정 대수는 각 Route에 대해 `ceil((end - begin) / period)`로 고정하고, SUMO flow의 `number`와 `period`로 출력합니다. 이 때문에 유한 시간의 실제 대수·비율은 명목 시간당 수요율과 조금 다릅니다. 실제 출발은 0.2초 simulation step과 SUMO의 안전 삽입 조건을 따릅니다. 이전 `{period: 30, end: 180}` 형식의 설정도 지원합니다.

생성된 `manifest.json`에는 Route 분류와 실제 적용 수요율·간격·예정 대수가 기록됩니다. `build/` 파일은 직접 편집하지 않습니다.

## 12개 Route 분류

분류는 공간상 교차가 아닌 실제 연결 junction 기준입니다. Merging은 둘 이상의 진입 edge, Diverging은 둘 이상의 진출 edge를 갖는 junction 통과를 뜻합니다.

| Route | 합류 junction | 분기 junction | weave 통과 / 필수 차로 교환 |
|---|---|---|---|
| `N_S` | S_MERGE | N_SPLIT | 아니오 |
| `S_N` | N_MERGE | S_SPLIT | 아니오 |
| `pink` | WEAVE_IN | N_SPLIT, WEAVE_OUT, E_SPLIT | 통과 / 필요 |
| `N_E_main` | WEAVE_IN, E_MERGE | N_SPLIT, WEAVE_OUT, E_SPLIT | 통과 / 필요 |
| `N_W` | WEAVE_IN, W_MERGE | N_SPLIT, WEAVE_OUT | 통과 / 불필요 |
| `green` | WEAVE_IN, W_MERGE | S_SPLIT, WEAVE_OUT | 통과 / 필요 |
| `S_E_ramp` | WEAVE_IN | S_SPLIT, WEAVE_OUT, E_SPLIT | 통과 / 불필요 |
| `S_E_main` | WEAVE_IN, E_MERGE | S_SPLIT, WEAVE_OUT, E_SPLIT | 통과 / 불필요 |
| `W_E` | E_MERGE | W_SPLIT | 아니오 |
| `E_W` | W_MERGE | 없음 | 아니오 |
| `W_N` | N_MERGE | W_SPLIT, W_RAMP_SPLIT | 아니오 |
| `W_S` | S_MERGE | W_SPLIT, W_RAMP_SPLIT | 아니오 |

분홍 방향은 weave 차로 3으로 들어오며 동쪽으로 나가려면 0~2로 이동해야 합니다. 초록 방향은 0~2로 들어오며 `upper_loop`로 나가려면 차로 3으로 이동해야 합니다. 나머지 weave 경로도 앞차 추종과 gap 형성에 참여하지만 경로 자체가 차로 교환을 요구하지는 않습니다.

## 실제 실행 결과

Windows, Python 3.12.9, SUMO 1.27.1, seed 21, 투입 예정 180초, 검증 한도 600초입니다. `sigma=0`, `speedDev=0`인 기존 결정적 HV 모델을 유지했습니다. 여러 seed의 통계적 일반화를 주장하지 않습니다.

[전체 비교 JSON](traffic_comparison.json), [요약 CSV](traffic_comparison.csv), [회귀 검증·기준 동등성 JSON](traffic_checks.json), [과부하 비교 JSON](traffic_stress.json)을 보존했습니다. 전체 궤적·차로 변경·trip·충돌 XML·SUMO 로그는 로컬 `scenarios/toegyewon/build/verified/`와 `build/stress/`에 있습니다.

| 조건 | 예정/완료 | 전체/ weave 차로 변경 | 양 방향 weave 동시 체류(초) | 타 방향 앞차 추종(차량·초) | 급제동 에피소드 | 전체 평균 속도(m/s) | 충돌/Teleport |
|---|---:|---:|---:|---:|---:|---:|---:|
| 이전: 30초 균등 | 74/74 | 70 / 32 | 5.4 | 1.0 | 6 | 13.22 | 0/0 |
| 낮음 + 집중 | 74/74 | 82 / 42 | 5.4 | 1.0 | 1 | 12.56 | 0/0 |
| 보통 균등 | 176/176 | 117 / 78 | 108.2 | 22.4 | 6 | 9.08 | 0/0 |
| **보통 + 집중(기본)** | **176/176** | **157 / 101** | **105.4** | **49.6** | **9** | **12.13** | **0/0** |
| 높음 + 집중 | 346/346 | 401 / 157 | 351.6 | 173.2 | 3 | 5.49 | 0/0 |

모든 정규 조건의 예정 차량 완료율은 100%, 종료 시 미진입·미완료 차량은 0이며 SUMO 실행 경고는 없었습니다. 보통 균등과 집중은 총 대수가 같지만, 집중에서 weave 내 주변 차량이 있는 차로 변경은 62→92회, 타 방향 앞차 추종은 22.4→49.6 차량·초로 늘었습니다. 단순 통과 대수 증가 외에 차량 간 접촉 기회가 늘었다는 증거입니다. 앞차 관측만으로 양보 의도를 판정하지는 않습니다.

평균 속도는 정지·미완료 차량을 포함한 모든 차량·시간 샘플의 평균입니다. 서로 다른 Route 구성과 출발 위상이 결과에 영향을 주므로 교통량에 따라 모든 지표가 단조롭게 변하지 않습니다. 급제동은 `acceleration < -4.5 - 1e-6 m/s²`로 진입하는 연속 구간당 1회이며, 정상 설정 decel=4.5에서의 부동소수점 오차를 제외합니다. 기준값은 `validation.hard_braking_threshold`로 바꿀 수 있습니다. JSON/CSV에는 출발 100대당 급제동, Route별 예정/출발/완료, 차로 변경 이유, edge별 속도·정지량도 포함됩니다.

### 30.16m weave의 고밀도 한계

| 지표 | 이전 | 보통 집중 | 높음 집중 |
|---|---:|---:|---:|
| weave 평균 속도(m/s) | 10.62 | 10.60 | 3.23 |
| weave 정지량(차량·초) | 0.2 | 0.2 | 656.2 |
| weave 동시 정지 차량 최댓값 | 1 | 1 | 8 |
| green_approach 동시 정지 차량 최댓값 | 0 | 0 | 42 |
| 완료 차량 평균 출발 지연(초) | 0.00 | 0.00 | 8.93 |
| 완료 차량 최대 출발 지연(초) | 0.0 | 0.0 | 142.7 |
| 마지막 차량 완료 시각(초) | 265.6 | 286.8 | 472.0 |

높음에서 공유 구간과 진입로의 병목 징후가 명확합니다. weave 최소 가속도는 기존부터 −5.33m/s²였고 높음에서도 동일했습니다. 높음의 네트워크 전체 최저 −7.00m/s²는 **`east_curve`**에서 발생했습니다. 따라서 고밀도의 모든 급감속을 30m weave 길이 하나의 영향으로 단정할 수 없습니다. 짧은 필수 차로 교환 구간과 후속 분기·차로 감소가 함께 작용하는 모델입니다. 높음에서 급제동 횟수가 더 적더라도 저속 대기열과 지연이 커졌으므로 더 안전하다는 뜻은 아닙니다.

추가로 `high × scale 2`를 실행하면 600초에 686대 중 579대만 완료(**84.40%**), 107대가 도로에 남습니다. 충돌·Teleport·SUMO 경고는 여전히 0입니다. 이 조건을 포함한 아래 명령은 보고서를 모두 기록한 뒤 미완료 수요로 **종료 코드 1**을 반환하는 것을 확인했습니다.

```powershell
python toegyewon.py compare --demand-scale 2 --output scenarios/toegyewon/build/stress
```

Teleport는 기존처럼 비활성화(-1)되어 있습니다. 따라서 0이라는 값만으로 정체가 없다고 판단하면 안 됩니다. 주행 완료율의 분모는 출발 차량만이 아니라 **미진입 차량까지 포함한 전체 예정 대수**입니다. 미완료 trip 출력도 활성화했으며, 완료 trip만의 지연 통계와 미완료·미진입 대수를 함께 제공합니다.

기하 변경 없이 기본 보통 집중 조건에서는 상호작용을 늘리면서 완주를 유지했습니다. 현장 차량 궤적·차로 유도선 자료가 없으므로 급제동의 현실성을 확정할 수 없으며, 높음 조건을 실도로 용량이나 안전성의 검증값으로 해석해서는 안 됩니다.

### 기존 시나리오 보존 확인

- 수정 전 코드로 `build/before`에서 실제 검증을 실행했습니다. 74/74 완료, 두 차량 weave 체류 중첩 3.6초, 모두 충돌·Teleport 0이었습니다.
- 새 코드의 baseline과 수정 전 실행의 출발/도착 ID, weave 기록, 차로 변경 기록, 차량별 최소 가속도, 궤적 샘플 수가 정확히 일치했습니다.
- 새/이전 manifest의 모든 edge 형상·노드·Route·차로 연결이 같고, XML 주석을 제외한 SUMO net XML 전체도 일치했습니다. 외부 edge 25개, 연결 60개, weave 30.16m입니다.
- 새 기본값의 `validate`: 분홍 단독 1/1, 초록 단독 1/1, 두 차량 2/2, 12 Route 12/12, 배경 176/176 완료. 두 차량 체류 중첩 3.6초와 기존 감속 재현, 금지 edge 차로 변경 없음.
- `validate` 후 `build/pair.sumocfg`를 SUMO-GUI에서 열면 배경 없이 원래 두 색상 테스트를 볼 수 있습니다. GUI 자체의 화면 검사는 하지 않았으며 수치는 headless SUMO/TraCI 실측입니다.

## 변경 파일과 계측 근거

- `config.json`: 단계별 기본 수요, Route 가중치, weave 집중, 검증 기준.
- `traffic.py`: 수요 계산·입력 검사·Route 분류만 분리. 도로 생성은 기존 `network.py`에 유지.
- `network.py`: 수요 계획을 XML/manifest에 반영. 기하·연결 생성과 HV 모델 속성은 유지.
- `validate.py`: 미완료 포함 지표, 단계별 비교, 과부하 실패 판정. TraCI 읽기 구독으로 궤적 수집 비용 감소. 차량 제어 API는 사용하지 않음.
- `toegyewon.py`: 단계/배수/seed CLI와 `compare` 추가.
- `test_traffic.py`: 수요 정규화·기존 수요 재현·입력 오류·경로 분류·미진입/급제동 계측 회귀 테스트 6개.
- 이 문서, 결과 JSON/CSV 및 README 링크: 실행과 검토 근거 보존.

SUMO 공식 문서의 [차로 변경 출력](https://sumo.dlr.de/docs/Simulation/Output/Lanechange.html)에 따라 변경 이유와 주변 gap을 기록하고, [TripInfo](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html)의 출발 지연·timeLoss·미완료 출력을 사용합니다. 출발 예약량과 실제 삽입은 다를 수 있으므로 [차량 삽입](https://sumo.dlr.de/userdoc/Simulation/VehicleInsertion.html) 설명에 맞춰 별도로 계측합니다.

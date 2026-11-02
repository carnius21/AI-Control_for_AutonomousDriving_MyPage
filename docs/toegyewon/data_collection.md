# 퇴계원IC POMDP 데이터 수집

2026-11-02, 로컬 `ljj`. 실제 headless SUMO와 관측 전용 휴리스틱으로 수집했다. 학습·Commit·Push는 하지 않았다. 기본 조건 3개 에피소드의 **1,888개 전이**가 모두 도착했고, 별도 혼잡 조건 984개 전이는 시간 초과로 끝났다. 성공 사례만으로 정책 성능이나 Offline RL 학습 성능을 주장하지 않는다.

## 1. 파일과 원본 재사용

| 파일 | 역할 |
|---|---|
| `collect_toegyewon_data.py` | 전용 CLI; 고속도로 수집기를 import하거나 실행하지 않음 |
| `scenarios/toegyewon/data_collection.py` | 환경·정책 연결, 실제 전이 수집, 메타데이터, 시드, 재개 |
| `scenarios/toegyewon/data_io.py` | JSONL gzip, 고정형 NPZ, 검증 가능한 shard, 엄격한 next 복원 |
| `scenarios/toegyewon/validate_data.py` | 체크섬·형식·시간 연결·상태·이벤트·보상·NPZ 일치·재현성 |
| `scenarios/toegyewon/behavior.py` | 학습하지 않은 결정적 관측 전용 휴리스틱 v2 |
| `scenarios/toegyewon/av_env.py` | 선택적 차량 상태 subscription/getter, trace 생략 옵션 추가 |
| `scenarios/toegyewon/test_data.py` | 경계·손상·shard·휴리스틱 단위 시험 |
| `docs/toegyewon/check_data_recovery.py` | 실제 SUMO 1 step 후 연결 예외 주입·재개·손상 검사 재실행 도구 |

수업의 [평가 문서](https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving/blob/main/project_materials/6_Project_Evaluation.md), [원본 수집기](https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving/blob/main/collect_pomdp_data.py), 로컬 `collect_pomdp_data.py`를 확인했다. 원본의 nested action/event, JSONL gzip, 고정형 NumPy 배열, 가변 감지 목록의 `detected_xy`/`detected_offsets`, 현재→step→다음 상태 수집 순서를 재사용했다. 원본을 import하면 고속도로 환경·학습 모듈 의존성을 불러오므로 저장 패턴을 전용 모듈로 작게 구현했다. 원본의 전체 전이 메모리 적재와 경계 검사 없는 next 복원은 사용하지 않는다.

기존 `env/`, PPO/BC/Offline RL 학습 코드, `collect_pomdp_data.py`, `data/dataset.npz`, OSM 원자료, 도로 기하·차로 연결은 이번 수집 작업에서 수정하지 않았다. build 파일은 `network.build()`와 `write_demand()`로 생성했다. 이전 교통·버스·AV 변경사항도 보존했다. 기존 `.gitignore`가 `data/toegyewon/`을 이미 제외하므로 변경할 필요가 없었다.

## 2. 19개 필수 항목의 실제 위치

모든 전이의 JSONL에 아래 항목을 저장한다. 이 writer는 중간 전이에도 next를 명시해 복원 의존성을 없앴다.

| 항목 | 의미/형식 | NPZ |
|---|---|---|
| `episode` | run 내부 에피소드 정수, 0부터 | int64 |
| `t` | AV 삽입 후 전이 번호, 0부터 | int64 |
| `observation` | 정책에 실제 전달한 float32 벡터 | `(N,43)` 또는 `(N,31)` float32 |
| `action_raw` | 실제 제출한 `[가감속, 차로]` | `(N,2)` float32 |
| `action.accel_raw` | raw[0], [-1,1] | action_raw[:,0] |
| `action.lane_change_raw` | raw[1], [-1,1] | action_raw[:,1] |
| `action.lane_change` | ≥0.5: +1, ≤-0.5: -1, 나머지 0 | int8 |
| `action.lane_change_applied` | 안전 게이트 통과 후 TraCI 요청 제출 여부 | JSONL |
| `reward` | 환경 step이 반환한 실제 보상 | float64 |
| `terminated` | 도착·충돌·teleport·경로 이탈·예상 밖 제거 | bool |
| `truncated` | 설정한 절대 SUMO 시각 제한 | bool |
| `state` | 행동 직전 실제 전체 차량 snapshot | JSONL |
| `detected_vehicles` | 같은 관측 frame의 선택된 주변 차량 목록 | 좌표는 detected_xy/offsets |
| `event.collided` | AV 충돌 | JSONL bool |
| `event.arrived` | 기대 경로를 따라 목적지 도착 | JSONL bool |
| `event.lane_before` | 행동 전 차로 index | JSONL int |
| `event.lane_after` | 행동 후 차로 index, 제거 시 `"absent"` | JSONL int/string |
| `next_observation` | step 반환 벡터 그대로 | float32 |
| `next_state` | step 직후 실제 world snapshot | JSONL |

NPZ는 위 11개 요구 key를 포함하고 object 배열 없이 `allow_pickle=False`로 읽힌다. `detected_offsets[i]:detected_offsets[i+1]`이 i번째 전이의 `(x,y)` 행이다. 좌표는 절대 로컬 위치이며 상대 좌표가 아니다. JSON은 관측·행동을 소수 몇 자리로 반올림하지 않아 float32 정책 입력을 그대로 복원한다. 상태도 반올림하지 않는다.

## 3. Observation 19/31/43 차이

평가 문서에는 19차원이 있으나, 현재 [수업 mdp_config.py](https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving/blob/main/env/mdp_config.py)와 로컬 구현은 5개 차로 슬롯의 31차원이다. 19는 3개 슬롯을 쓰는 이전 설명 `1+3×4+3+3`과 부합하지만, 현재 코드에서 실제 19차원 환경을 검증한 것은 아니다. 임의 19차원 변환을 제공하지 않는다.

인덱스는 Python 0-based, 구간 끝 제외다. 기본 schema는 `toegyewon-route43-v1`. legacy는 `highway-layout31-adapter-v1`이며 도로 세계 X축 대신 연결 관계와 차로 기준 거리를 사용하는 어댑터이므로 단순 차원 일치가 고속도로 정책의 유효성을 뜻하지 않는다.

| 인덱스 | 의미 |
|---|---|
| 0 | AV 속도 / 33.33 m/s |
| 1:21 | 상대 차로 `+2,+1,0,-1,-2`별 선행 gap, 선행 상대속도, 후행 gap, 후행 상대속도 |
| 21:26 | 각 차로 연결 여부/끝까지 남은 거리, 없는 차로 -1 |
| 26:31 | 각 차로의 국소 밀도 |
| 31:36 | 다음 route edge로 이어지는 차로인지 |
| 36 | 현재 차로 남은 거리 / visibility |
| 37 | SUMO best lane offset / 4 |
| 38 | 차로 index / max(1, 차로 수-1) |
| 39 | route index / max(1, route edge 수-1) |
| 40 | 허용 속도 / 33.33 m/s |
| 41 | 내부 교차로 flag |
| 42 | bestLanes 기준 유효 남은 거리 / visibility |

거리 정규화 기본값은 50 m, 모든 값은 [-1,1]로 clip한다. 선행 gap은 양수, 후행 gap은 음수이며 종방향 겹침은 관측 gap 0과 진단용 음수 `bumper_gap`으로 구분한다. 선행 부재는 `[1,1]`, 후행 부재는 `[-1,-1]`이다. schema·dimension·정규화 상수·각 index 설명은 `metadata.json`에도 저장한다.

## 4. 행동·보상·상태

휴리스틱 v2는 **관측 벡터만** 읽는다. 허용속도의 80%를 목표로 하되 현재 차로 선행차의 간격·상대속도에 따라 감속하고, 짧은 구간에서 필요한 차로 수에 비례해 속도를 낮추며 route 방향을 요청한다. 실제 2차원 행동을 `external` 인터페이스에 제출한다. SUMO baseline에 가상의 행동을 붙이지 않는다. `--policy sumo`는 수집 CLI에서 허용하지 않는다.

정규화 가감속은 차량 accel/decel로 환산된다. 현재 AV는 양수×2.6, 음수×4.5 m/s²이며 속도 요청은 현재 속도+가속도×0.2 s이다. 차로 요청은 기존 도로·권한·차간 간격 게이트를 거친다. speedMode 31, laneChangeMode 1621을 유지하므로 SUMO의 안전 제어와 전략적·협조적 차로 변경이 함께 작동한다. 요청 속도와 실제 속도가 같다고 보장하지 않는다.

`lane_change_applied`는 제출 사실이며 완료 판정이 아니다. `event.lane_changed`는 같은 edge 내 차로 ID의 실제 변화다. edge 전환에 따른 index 변화는 차로 변경으로 세지 않는다. 이 이벤트만으로 정책 요청과 SUMO 자율 변경의 인과를 확정하지 않는다. 추가 필드로 거절 이유, 요청 가속도/속도, 다음 frame의 실제 가속도, lane delta를 남긴다. 예를 들어 기본 green에서는 요청 제출 0회인데 실제 변경은 3회였다.

보상은 기존 ToegyewonEnv 정의를 그대로 사용한다: 실행 중 `0.1×속도/허용속도`, 선행 gap<6 m이면 -0.1, 요청 거절 시 -0.02. 도착 종료는 2, 다른 종료/시간 초과는 -5로 대체한다. 수집기가 보상을 새로 만들지 않는다. `terminated`와 `truncated`를 합치지 않고 보존한다. bootstrap 시 시간 초과의 처리 방식은 학습 알고리즘이 명시적으로 정해야 한다.

state는 현재 삽입된 모든 차량의 ID·종류·xy·속도·가속도·허용속도·edge/lane·차로 위치·길이·route·목적지·route index·AV 상대 위치/속도/유클리드 거리를 포함한다. 아직 출발하지 않은 수요는 world 차량 목록이 아니라 metadata의 config/demand에 있다. `state.time`은 실제 SUMO 초이며 `t`와 다르다. 도착 제거 후 `next_state.ego=null`, `ego_alive=false`, next observation은 환경 반환값인 0 벡터다. 시간 초과 때 AV가 살아 있으면 실제 위치와 관측을 유지한다. 이전의 `last_state`를 terminal state로 재활용하지 않는다.

`detected_vehicles`는 observer가 관측 특징을 만드는 데 선택한 최근접 선행/후행 차량을 ID별로 중복 제거한 목록이다. 밀도 값에 기여한 모든 차량이나 모든 센서 원시 point를 뜻하지 않는다. ID·종류·길이·xy는 진단 annotation이며 정책 입력을 늘리지 않는다. BUS 길이는 12 m, HV/AV는 5 m다.

좌표는 WGS84(lon,lat)를 EPSG:32652로 투영한 다음 설정 원점 `(127.131,37.636)`의 투영 xy를 뺀 로컬 m 단위다. netconvert의 좌표 정규화는 비활성화되어 있다. projected origin 값은 metadata에도 저장한다. 속도 m/s, 가속도 m/s², 시간 s다.

## 5. 실제 결과와 위치

근거: [전체 실행·재현성 보고서](data_collection_checks.json), [중단 복구 보고서](data_recovery_checks.json), [전체 1개 전이 샘플](data_sample.json).

| `data/toegyewon/` 하위 run | episode / transition | 종료 | 평균 Return | 실제 차로 변경 |
|---|---:|---|---:|---:|
| `pink_final` | 2 / 1,284 | 도착 2 | 41.590948 | 각각 3 |
| `green_final` | 1 / 604 | 도착 1 | 41.836587 | 3 |
| `green_stress_final` | 1 / 984 | 시간 초과 1 | 0.998254 | 2 |
| `recovery_final` | 1 / 3 | 의도한 짧은 시간 제한 | -5.037792 | 0 |
| `pink_reproduction` | 2 / 1,284 | 도착 2 | 41.590948 | 각각 3 |

기본 3개 episode 성공률 100%, 충돌률 0%. 혼잡 green까지 포함한 4개 episode는 성공률 75%, 충돌률 0%이며 **2,872개 전이**다. 회복 시험은 3개를 추가 수집했고, 중단 시도의 미완료 1개는 별도 보존했다. 재현 run의 1,284개는 동일 데이터이므로 다양성 증가로 계산하지 않는다. 모든 위 run의 SUMO collision·teleport 목록은 비어 있다. 이 표를 대규모 일반 성능 추정으로 해석할 수는 없다.

기본값: medium, weave factor 2, BUS 0.1, 출발 90 s, 0.2 s step, 43차원, seed=21+episode. 배경 수요는 HV 158/BUS 18이며 pink·green 테스트 차량은 유지된다. 각 snapshot에 HV/BUS/AV가 실제 존재함을 검사했다. pink 2개는 seed 21/22에도 같은 주행이었다. 현재 sigma=0, speedDev=0과 결정적 수요 배치이므로 seed 변경만으로 다양성이 생기지 않는다. 조건별 별도 run을 사용해야 한다.

green 기본 episode에서 BUS 감지 차량-전이 709건, weave BUS 감지 51건이다(고유 버스 수 아님). 20 m 이내 BUS 이웃이 있던 weave 시간은 10.0 s였다. 실제 sample의 episode=0,t=262, time=142.6 s에서 AV는 weave_2, 1.0564 m/s이고, 12 m 버스 `bus_green.9`가 4.9426 m 앞에서 정지해 상대속도 -1.0564 m/s였다. 차로 +1 요청은 insufficient_gap으로 거절됐고 다음 실제 가속도는 -0.5165 m/s²였다.

다음은 저장된 sample의 일부다. 전체 43개 관측값과 전체 차량 상태는 링크한 JSON에 있다.

```json
{
  "episode": 0,
  "t": 262,
  "action_raw": [-0.11477869004011154, 1.0],
  "action": {
    "accel_raw": -0.11477869004011154,
    "lane_change_raw": 1.0,
    "lane_change": 1,
    "lane_change_applied": false,
    "rejection": "insufficient_gap"
  },
  "reward": -0.1114210916161511,
  "terminated": false,
  "truncated": false
}
```

green stress는 출발 103 s, 제한 300 s다. weave에서 BUS 감지 36건과 740회 요청 거절이 있었고 빠져나오지 못했다. 짧은 약 30 m weave에서 필요한 차로 교차와 주변 정체가 겹치는 병목이 여전히 존재한다. 데이터를 성공으로 바꾸거나 geometry/안전 게이트를 완화하지 않았다. 휴리스틱 v1의 pink 실패(`pink_smoke`, 2,549개 timeout), v2 예비 run(`pink_v2`,642개 도착; `green_v2`,984개 timeout)도 로컬에 보존했으며 최종 표에는 합산하지 않았다. v2의 기본 사례 최저 가속도는 약 -4.5 m/s²다. 병목 해결이나 휴리스틱의 전 조건 안정성을 이번 결과가 보장하지 않는다.

파일 예:

```text
data/toegyewon/green_final/metadata.json
data/toegyewon/green_final/summary.json
data/toegyewon/green_final/validation.json
data/toegyewon/green_final/episodes/000000/complete.json
data/toegyewon/green_final/episodes/000000/attempt_000/episode.json
data/toegyewon/green_final/episodes/000000/attempt_000/shard_00000.jsonl.gz
data/toegyewon/green_final/episodes/000000/attempt_000/shard_00000.npz
data/toegyewon/green_final/episodes/000000/attempt_000/shard_00000.json
```

green은 256+256+92개로 3개 shard, pink 각 episode는 256+256+130개다. NPZ와 JSONL이 1:1 대응한다. SUMO XML/로그는 각 attempt의 `sumo/`에 있다. AV 도착 시 수집을 끝내므로 아직 운행 중인 배경 차량이 있는 것은 정상이다.

## 6. 검증과 중단 처리

단위 시험 18개 통과(기존 AV·교통 시험 포함). 실제 저장 파일을 다시 읽어 모든 필수 필드, 관측 차원·범위, action 범위·변환, bool, 유한 보상, current/next의 0.2 s 간격, episode/t 연속성, shard 사이 state/observation 일치, 현재 ego·감지 차량의 world 일치, 도착 제거, 종료·시간 초과·보상, NPZ 모든 배열의 dtype·값을 검사했다. 모든 shard의 SHA256도 검사한다.

동일 설정 pink 2개 episode를 새 SUMO 프로세스에서 재수집해 **1,284개 전이 전체가 정확히 같음**을 확인했다. run_id만 제외하고 전체 world와 감지·이벤트까지 비교했다. gzip header 시각이나 run UUID 때문에 압축 파일 byte 자체가 같은지를 요구하지 않는다.

각 shard는 `.partial`에 쓰고 파일을 닫은 뒤 rename하며 체크섬 marker를 마지막에 기록한다. 실제 종료 후 episode complete marker를 만든다. 중간 next 생략 형식도 reader가 읽을 수 있지만 같은 episode의 t+1에서만 복원하고, terminal·파일 끝·빠진 step·episode 경계·한쪽 next만 있는 경우에는 오류를 낸다. gzip CRC/잘린 파일도 실패한다. 이번 writer는 모든 next를 직접 저장하므로 shard 하나만 읽어도 마지막 전이의 실제 next가 있다.

실제 첫 전이 뒤 `ConnectionError`를 주입한 시험에서 1개를 미완료 attempt에 보존했다. `--resume`은 같은 episode/seed를 새 attempt에서 다시 실행했고, 이전 기록과 이어 붙이지 않았다. 완료된 episode는 checksum/연결 검사 후 건너뛴다. 파일 손상을 주입하면 거부함도 확인했다. 초기 AV 삽입 실패나 step 중 연결 소실은 실패 기록을 남기며 가짜 terminal/next를 생성하지 않는다. 예기치 않은 AV 제거가 step에서 관찰되면 실제 terminal 상태로 저장한다.

강제 프로세스 종료/전원 차단 실험은 하지 않았다. hard kill은 아직 메모리에 있는 최대 shard-size개의 전이를 잃을 수 있고, marker 없는 파일은 완료 데이터가 아니다. 동일 output directory의 동시 writer는 지원하지 않는다. 저장장치 고장에 대한 fsync/트랜잭션 보장은 없으므로 완료 shard도 별도로 백업해야 한다.

## 7. Windows CMD 명령

프로젝트 루트에서 실행한다. output은 새 디렉터리여야 한다.

```bat
python collect_toegyewon_data.py --episodes 2 --policy heuristic --av-route pink --traffic medium --bus-ratio 0.1 --seed 21 --out-dir data/toegyewon/my_pink --validate
python collect_toegyewon_data.py --episodes 1 --av-route green --out-dir data/toegyewon/my_green --validate
python collect_toegyewon_data.py --episodes 1 --av-route green --av-depart 103 --time-limit 300 --out-dir data/toegyewon/my_stress --validate
python collect_toegyewon_data.py --out-dir data/toegyewon/my_pink --validate-only
python collect_toegyewon_data.py --out-dir data/toegyewon/pink_reproduction --validate-only --compare-with data/toegyewon/pink_final
python collect_toegyewon_data.py --episodes 2 --out-dir data/toegyewon/my_pink --resume --validate
python -m unittest scenarios.toegyewon.test_data scenarios.toegyewon.test_av scenarios.toegyewon.test_traffic
python -m docs.toegyewon.check_data_recovery data/toegyewon/my_recovery
```

resume는 원래 옵션·코드·OSM·SUMO 버전·network/manifest checksum이 같아야 한다. episode 수까지 동일해야 하며 이미 끝난 run을 연장하는 옵션은 없다. 수정 후에는 새 run으로 수집한다. `--time-limit`은 AV 주행 duration이 아니라 절대 SUMO 시각이다.

`--traffic low|medium|high`, `--weave-factor`, `--bus-ratio`, `--av-depart`, `--observation route|legacy`, `--shard-size`를 지원한다. Route별 가중치와 demand scale은 복사한 설정 파일의 `traffic.route_weights`, `traffic.scale`을 수정하고 `--config path.json`으로 전달한다. 수집 환경과 수요 설정 전체가 metadata에 남는다.

호환되는 실제 체크포인트가 있을 때만 `--policy ppo --checkpoint path.pth --observation route`를 사용한다. 기존 strict loader로 dimension/schema/state_dict를 검사하며 임의 신경망을 생성해 결과를 내지 않는다. 실제 학습된 checkpoint가 없어 이번에는 PPO 수집을 실행하지 않았다. 31차원은 명시적 legacy 선택이 필요하고 43으로 padding하지 않는다.

기존 GUI 명령은 유지된다:

```bat
python toegyewon.py gui --traffic medium --bus-ratio 0.1 --av sumo --av-route pink
```

이는 SUMO baseline 시각화이며 이번 외부 휴리스틱 rollout과 동일 제어가 아니다. 수집은 headless다. 기존 `validate`, `validate-bus`, `validate-av` CLI도 유지한다. GUI 화면을 이번 데이터 수집 시험에서 재확인하지는 않았다.

읽기 예:

```python
import numpy as np
from scenarios.toegyewon.data_io import iter_transitions
path = 'data/toegyewon/green_final/episodes/000000/attempt_000/shard_00000'
for transition in iter_transitions(path + '.jsonl.gz'):
    pass
with np.load(path + '.npz', allow_pickle=False) as z:
    o, a, r, nxt = z['observation'], z['action_raw'], z['reward'], z['next_observation']
    terminated, truncated = z['terminated'], z['truncated']
```

실제 학습용 loader는 먼저 `validate_dataset()`을 실행하고 `complete.json`이 가리키는 attempt만 사용해야 한다. 전체 attempt를 glob해서 합치면 중단 시도와 재수집이 중복된다. 서로 다른 run을 합칠 때 `(run_id,episode,t)`로 식별하고 metadata를 함께 유지한다.

## 8. 대규모 수집 범위와 한계

10^7개를 수집하지 않았다. 전이 메모리는 shard 크기와 활성 차량 수에 제한되며 전체 전이를 RAM에 적재하지 않는다. 기본 shard는 256개이고 episode 요약 목록만 episode 수에 비례해 증가한다. 읽기/검증도 shard 단위다. full state+next를 모두 넣어 크기가 커지는 대신 명시적 복원을 선택했다. 현재 green 전체 run은 약 8.65 MB/604전이이며 압축 shard의 정확한 byte 수는 실행 보고서에 있다. 단순 전체 run 비례 추정은 10^7개에 약 143 GB지만 차량 수·반복도·에피소드 길이에 크게 좌우되며 실측 대규모 용량 보장은 아니다. 생산 수집 전 짧은 pilot로 압축 크기와 디스크 잔량을 측정해야 한다.

metadata에는 수집 UTC 시각, HEAD/dirty 상태, 관련 코드·OSM SHA256, config/checkpoint hash, SUMO/Python/NumPy 버전, seed 규칙, 조건, policy version, schema, 좌표계를 저장한다. 자동 multiprocessing dispatcher는 구현하지 않았다. 별도 output 디렉터리와 seed/조건으로 독립 CLI를 동시에 실행할 수 있고 이번 검증에서도 별도 SUMO 프로세스를 동시에 실행했다. 단일 run에 병렬 writer를 붙이지 않는다.

미검증: 실제 PPO checkpoint, legacy31 실제 rollout, low/high 모든 조건 조합, 실제 충돌 강제 생성, SUMO 프로세스 강제 kill/전원 장애, 장시간 10^7 수집, Offline RL 학습 성능. 이번 데이터는 관측 기반 behavior policy와 SUMO 안전 제어가 결합된 행동-결과 데이터이며 expert demonstration이 아니다. green 혼잡 timeout 및 초기 휴리스틱 실패는 현 환경·정책의 한계로 남겨 둔다.

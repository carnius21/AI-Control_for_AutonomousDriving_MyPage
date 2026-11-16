# POMDP 데이터셋 필수 포함 항목 및 팀 추가 항목 정리

> 기준 구현: [collect_pomdp_data.py](../../collect_pomdp_data.py), [env/sumo_env.py](../../env/sumo_env.py), [env/ic_experiment.py](../../env/ic_experiment.py), [env/navigation_clarity.py](../../env/navigation_clarity.py)  
> 저장 포맷: `.jsonl.gz` (전체 Transition + Dictionary) 및 `.npz` (학습용 배열)

---

## 1. 필수 포함 항목 체크표

| 필수 포함 항목 | 형태 | 의미 | 포함 여부 (o / x) | 비고 |
| :--- | :--- | :--- | :---: | :--- |
| `episode` | Integer | Episode 번호 | **o** | `record["episode"]`, `.npz["episode"]` |
| `t` | Integer | Episode 내부 timestep | **o** | `record["t"]`, `.npz["step"]` |
| `observation` | Vector (19-dim → 47-dim) | 시점 $t$에서 AV Policy가 실제로 입력받는 부분 관측 $o_t$ | **o** | 기본 스켈레톤 19-dim, 현재 퇴계원IC `ClarityEnv` 기준 47-dim |
| `action_raw` | Vector (2-dim) | Policy가 출력한 원본 Action [가감속, 차선변경] | **o** | `record["action_raw"]`, `.npz["action_raw"]` |
| `action.accel_raw` | Float | 환경에 적용된 가감속 Action 값 | **o** | `record["action"]["accel_raw"]` |
| `action.lane_change_raw` | Float | 환경에 적용된 차선변경 raw 값 | **o** | `record["action"]["lane_change_raw"]` |
| `action.lane_change` | Integer | 실제 명령으로 변환된 차선변경 값 `{-1, 0, +1}` | **o** | `record["action"]["lane_change"]`, `.npz["lane_change"]` |
| `action.lane_change_applied` | Boolean | 차선변경 명령이 실제 적용되었는지 여부 | **o** | `record["action"]["lane_change_applied"]` |
| `reward` | Float | 시점 $t$에서 받은 Reward $r_t$ | **o** | `record["reward"]`, `.npz["reward"]` |
| `terminated` | Boolean | 충돌 / 도착 등 환경 자체의 종료 여부 | **o** | `record["terminated"]`, `.npz["terminated"]` |
| `truncated` | Boolean | 최대 Episode Step 등 시간 제한에 의한 종료 여부 | **o** | `record["truncated"]`, `.npz["truncated"]` |
| `state` | Dictionary | SUMO 내부의 privileged simulator state $s_t$ | **o** | `ego_alive`, `ego_x/y/speed/lane/lane_id/road_id/lane_pos`, `vehicles` 전체 목록 |
| `detected_vehicles` | List | Observation 시점에 감지된 주변 차량 정보 | **o** | `{id, x, y, rel_pos, speed, lane_offset}` 리스트 (`.npz`는 `detected_xy`, `detected_offsets`) |
| `event.collided` | Boolean | 해당 step에서 충돌 발생 여부 | **o** | `record["event"]["collided"]` |
| `event.arrived` | Boolean | 목적지 도착 여부 | **o** | `record["event"]["arrived"]` |
| `event.lane_before` | Integer / String | Action 적용 전 AV 차선 | **o** | `Integer` (SUMO lane index) |
| `event.lane_after` | Integer / String | Action 적용 후 AV 차선 | **o** | `Integer` (SUMO lane index) |
| `next_observation` | Vector (19-dim → 47-dim) | 다음 시점의 부분 관측 $o_{t+1}$ | **o** | `.npz` 전 스텝 저장, `.jsonl.gz`는 종료 스텝 기록 후 `iter_transitions()`로 복원 |
| `next_state` | Dictionary | 다음 시점의 privileged simulator state $s_{t+1}$ | **o** | `.jsonl.gz` 종료 스텝 기록 후 `iter_transitions()`로 전 스텝 자동 복원 |

---

## 2. 팀별 추가 항목 (`ICExperimentEnv` / `ClarityEnv` 기준)

| 팀별 추가 항목 | 형태 | 의미 |
| :--- | :--- | :--- |
| `observation` 확장 (`19 → 47-dim`) | Vector (47-dim) | 5차로 거리/상대속도/연결성/밀도 + IC 경로 안내(진입·분기 거리, 목표 차로 방향, 제한속도, 램프/지퍼 상태 등) |
| `event.route` | String | 현재 에피소드 지정 경로 ID (`route_01` ~ `route_16`) |
| `event.sumo_seed` | Integer | 해당 에피소드의 SUMO 교통류 시드 번호 |
| `event.prep100` | Boolean | 분기점 전 100m 사전 차로 준비 구간 진입 여부 |
| `event.route_lane_ready` | Boolean | 현재 차로가 목적지 경로의 다음 도로와 연결되는지 여부 |
| `event.exit_lane_change_distance_m` | Float / Null | 출구/분기점 기준 차선 변경이 완료된 잔여 거리(m) |
| `event.zipper_count` | Integer | 에피소드 내 지퍼 합류 통과 횟수 |
| `event.zipper_compliant` | Boolean / Null | 지퍼 합류 규칙(교대 합류) 준수 여부 |
| `event.ramp` | Boolean | 현재 위치가 램프(`_link`) 구간인지 여부 |
| `event.ramp_excess_mps` | Float | 램프 제한속도 초과 속도(m/s) |
| `event.wrong_exit` | Boolean | 충돌 없이 잘못된 출구/경로로 빠져 종료되었는지 여부 |
| `event.reward_components` | Dictionary | 스텝 보상의 세부 항목별 분해 (`base`, `early_prep`, `route_lane`, `zipper`, `ramp` 등) |

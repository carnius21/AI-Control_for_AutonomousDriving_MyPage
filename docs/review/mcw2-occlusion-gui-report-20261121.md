# 퇴계원IC 특수차량 2D 시야 가림(`--occlusion`) 및 차종별 GUI 시각화 리포트 (`mcw2`)

> 작성일: 2026-11-21 (커밋 `d0cb1fe` 이후 후속 작업)  
> 브랜치 / 러너: `mcw2` / `utils/mcw_train.py` (`47차원` 호환 `McwEnv`)  
> 최종 체크포인트: `results/mcw_runs/mcw2_occlusion_ppo/best_model.pt` (`sha256: 4dab15658aa3f858...`)  
> 평가 조건: **`--stage high_real_ratio --no-safety --visibility 120.0 --obs-noise --agenda2 --occlusion --occ-truck-rate 1.0 --occ-bus-rate 1.0 --occ-delivery-rate 0.5`**

---

## 1. 전체 실험 흐름 및 단계별 결과 요약 (`high_real_ratio`, 80에피소드)

| 단계 | 체크포인트 | 추가된 제약 / 변경사항 | 학습 방법 | 완주 (`Arrival`) | 충돌 (`Collision`) | 타임아웃 (`Timeout`) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **0. 안전게이트 제거** | `mcw2_nosafety_final/best_model.pt` | `--no-safety`, `50m`, 노이즈 OFF | DAgger v1·v2 블렌드 | 78/80 (97.5%) | 1/80 (1.2%) | 1/80 (1.2%) |
| **1. 안건 1 (시야·노이즈)** | `mcw2_120m_noise_final/best_model.pt` | `120m` + 거리비례 가우시안 노이즈 | DAgger + 블렌드(`alpha=0.45`) | 77/80 (96.2%) | 3/80 (3.8%) | 0/80 (0.0%) |
| **2. 안건 2 (내비 축소)** | `mcw2_agenda2_final/best_model.pt` | 목표차로 오프셋·400m·2nd마스크 제거 + `120m` Multi-hop `_lane_connectivity` | DAgger + PPO + 저LR DAgger 블렌드(`alpha=0.50`) | 78/80 (97.5%) | 2/80 (2.5%) | 0/80 (0.0%) |
| **3-a. 시야 가림 (적응 전)** | `mcw2_agenda2_final/best_model.pt` | **`--occlusion` ON** (트럭 100%, 버스 100%, 소형화물 50%) | *(적응 학습 없이 바로 평가)* | 76/80 (95.0%) | 4/80 (5.0%) | 0/80 (0.0%) |
| **3-b. 시야 가림 (적응 후)** | **`mcw2_occlusion_ppo/best_model.pt`** | 동상 + **순수 PPO 파인튜닝(`12,288` step)** | **순수 `--no-safety` PPO (`lr=2.5e-5`, 블렌딩 없음)** | **77/80 (96.2%)** | **3/80 (3.8%)** | **0/80 (0.0%)** |

> **투명 공개 (무엇이 바뀌고 무엇을 유지했는가):**
> - **유지한 것:** `--no-safety`(안전게이트 OFF), 보상 함수 구조, `_neighbor` 사각지대 패치, `47차원` 신경망 구조, `high_real_ratio` 차량 분포 확률(`승용 77% / 소형화물 18% / 트럭 4% / 버스 1%`).
> - **변경된 것:** 특수차량 2D 시선 가림(`--occlusion`), 발표용 GUI 차종별 색상 분리(`--color-by-type`, `--gui`, `--gui-delay`)를 [utils/mcw_train.py](file:///C:/Users/문시원/Artificial-Intelligence-and-Control-for-Autonomous-Driving/utils/mcw_train.py)에 추가했습니다.
> - **학습 계보:** `mcw2_agenda2_final/best_model.pt`에서 `--resume`해 `--occlusion` 환경에서 **DAgger·블렌딩 없이 순수 PPO(`12,288` step, `lr=2.5e-5`, `lane_entropy=0.0005`)만으로** `76/80 (충돌 4)` → `77/80 (충돌 3)`을 달성했습니다.

---

## 2. 특수차량 2D 시야 가림(`--occlusion`) 구현 방식

### ① 차종별 차등 가림 비율
- **`truck` (`truck_idm`, 9.0m×2.5m):** `100%` (`--occ-truck-rate 1.0`)
- **`bus` (`bus_idm`, 12.0m×2.5m):** `100%` (`--occ-bus-rate 1.0`)
- **`delivery` (`delivery_idm`, 5.5m×2.0m):** **`50%`** (`--occ-delivery-rate 0.5`)
  - `zlib.crc32(vid.encode()) % 1000 < rate * 1000` 해시로 차량 ID마다 **불투명 탑차(50%) vs 개방형 화물(50%)**을 고정 구분해 스텝 간 깜빡임(flicker) 없이 안정적으로 절반만 시야를 차단합니다.
- 일반 승용(`passenger`, `custom1`): `0%` (가리지 않음)

### ② 2D 시선 그림자 기하학 (`_segment_intersects_obb`)
1. `traci.vehicle.subscribeContext(ego_id, ..., visibility + 25m)`로 주변 차량의 위치·각도·길이·폭·차종(`VAR_VEHICLECLASS`)을 매 스텝 한 번에 조회합니다.
2. 자차 앞유리/센서 위치(`front - 1.2m`)에서 각 주변 차량 중심을 잇는 선분(`S -> T`)이 불투명 특수차량의 회전 직사각형(OBB `[-L/2, L/2] × [-W/2, W/2]`)을 통과(`0.0 <= t <= 0.999`)하면 **시야 가림(occluded)**으로 판정합니다.
3. `_get_obs()` 실행 중에만 `_occ_sensor_mask = True`를 켜 `_neighbor()`, `_scan_lane_neighbors()`, `_lane_density()`에서 가려진 차량을 제외하므로,
   - **에이전트 관측(`obs`)**은 실제로 트럭·버스 뒤나 대각선 옆 차선이 안 보이는 1인칭 시야가 되고,
   - **학습 보상(`use_ttc_reward`)**은 실제 물리 간격을 기준으로 충돌 위험을 패널티로 줄 수 있습니다.

### ③ 라이브 시뮬레이션 실측 작동 검증 (`route_05, 06, 11` 3에피소드)
- 총 주행 스텝 `1,391` 중 **`1,322`스텝(`95.0%`)**에서 120m 내 가림 차량이 존재 (`누적 박스 5,743개`)
- 관측 후보 차량 판정 `37,533`회 중 **`4,249`회(`11.3%`)가 실제 2D 시선 차단**으로 미감지 처리됨

---

## 3. 80회 다중시드 경로별 결과 비교 (적응 전 vs PPO 적응 후)

| 경로 | 적응 전 (`mcw2_agenda2_final`) | PPO 적응 후 (`mcw2_occlusion_ppo @12,288`) | 비고 |
| :---: | :---: | :---: | :--- |
| `route_01 ~ 04` | 각 5/5 | **각 5/5** | 20/20 완주 |
| **`route_05`** | 3/5 (충돌 `40305, 40405`) | **4/5** (충돌 `40305`) | 시야가림 추가 실패 `40405` 해결 |
| `route_06 ~ 12` | 각 5/5 | **각 5/5** | 35/35 완주 |
| **`route_13`** | 3/5 (충돌 `40213, 40313`) | **3/5** (충돌 `40313, 40413`) | `40213` 해결, `40413` 1건 발생 |
| `route_14 ~ 16` | 각 5/5 | **각 5/5** | 15/15 완주 |
| **합계** | **76/80 (95.0%) · 충돌 4** | **77/80 (96.2%) · 충돌 3 · 타임아웃 0** | **`eval_mcw2_occlusion_12288_80ep/eval_16routes.json`** |

---

## 4. 발표 영상용 차종별 시각 구분 (`VEHICLE_TYPE_COLORS` & `--gui`)

기존 `scenarios/hv_high15000_entryprep/highway.rou.xml`은 모든 `<flow>`에 `color="0.5,0.5,0.5"`가 지정되어 `sumo-gui`에서 차종 색이 모두 회색으로 보였습니다. `prepare_scenario(..., color_by_type=True)`에서 `<flow color=...>`를 제거하고 `<vType>`별로 색상을 부여했습니다(물리·확률·시드는 100% 동일 유지).

| 차종 (`vType`) | 길이 × 폭 | GUI 모양 (`guiShape`) | 표시 색상 (`R,G,B`) | 비고 |
| :--- | :---: | :--- | :--- | :--- |
| 자율주행 Ego (`ego_type`) | 4.8m × 1.8m | `passenger/sedan` | **빨강** (`1.0, 0.20, 0.25`) | `sumo-gui` 자동 추적 확대 |
| 대형 트럭 (`truck_idm`) | 9.0m × 2.5m | `truck` | **노랑** (`0.98, 0.78, 0.10`) | 100% 시야 차단 |
| 버스 (`bus_idm`) | 12.0m × 2.5m | `bus` | **파랑** (`0.18, 0.45, 0.98`) | 100% 시야 차단 |
| 소형 화물 (`delivery_idm`) | 5.5m × 2.0m | `delivery` | **청록** (`0.18, 0.78, 0.92`) | `--gui` 시 가리는 탑차=진한 청록 `(15,130,175)` / 투과 화물=연하늘 `(130,225,245)` |
| 비양보 승용 (`*_violator`) | 4.8m × 1.8m | `passenger/sedan` | **주황** (`1.0, 0.52, 0.12`) | `lcCooperative=0` |
| 일반 승용 (`car_*`) | 4.8m × 1.8m | `passenger` | **연회색** (`0.82, 0.84, 0.88`) | 일반 교통류 |

---

## 5. 재현 커맨드 및 검증

```bash
# 1) 단위 테스트 (기존 6 + 안건2 2 + 시야가림·색상 4 = 12/12 OK)
python -m unittest discover -s tests -v

# 2) 최종 모델 80에피소드 평가 재현 (high_real_ratio)
python -m utils.mcw_train --stage high_real_ratio --no-safety \
  --visibility 120.0 --obs-noise --agenda2 \
  --occlusion --occ-truck-rate 1.0 --occ-bus-rate 1.0 --occ-delivery-rate 0.5 \
  --resume results/mcw_runs/mcw2_occlusion_ppo/best_model.pt \
  --eval-only --eval-episodes 5 --name eval_mcw2_occlusion_12288_80ep

# 3) 발표 영상 녹화용 GUI 실행 (16개 경로 각 1회)
python -m utils.mcw_train --stage high_real_ratio --no-safety \
  --visibility 120.0 --obs-noise --agenda2 \
  --occlusion --occ-truck-rate 1.0 --occ-bus-rate 1.0 --occ-delivery-rate 0.5 \
  --gui --gui-delay 80 --eval-only --eval-episodes 1 \
  --resume results/mcw_runs/mcw2_occlusion_ppo/best_model.pt --name gui_demo
```

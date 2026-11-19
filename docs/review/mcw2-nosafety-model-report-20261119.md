# 퇴계원IC 안전게이트 제거(`--no-safety`) 모델 개선 및 80회 다중시드 검증 리포트 (`mcw2`)

> 작성일: 2026-11-19  
> 브랜치 / 러너: `mcw2` / `utils/mcw_train.py`, `utils/mcw_watch.py` (47차원 `ClarityEnv` + `RouteNavigation(horizon=400.0)`)  
> 최종 배포 체크포인트: `results/mcw_runs/mcw2_nosafety_final/best_model.pt` (`model.pt` 동일)  
> 안전게이트 설정: **`ACTION["lane_change_safety"]["enabled"] = False` (`--no-safety` 기본값)**  
> 목표 기준: 완주율 **≥ 95%**, 충돌률 **< 5%** (16개 경로 × 5시드 = 80회 다중시드 평가 기준)

---

## 1. 최종 검증 성적 요약 (`high_real_ratio`: 15,000 vph + 2025 실측 차종 비율)

| 모델 / 평가 조건 | 안전게이트 (`lane_change_safety`) | 시행 수 | 완주 (`Arrival`) | 충돌 (`Collision`) | 타임아웃 (`Timeout`) | 결과 파일 |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 기존 `stage3_high_v5_b` | ON (`--safety`) | 80회 | 78/80 (97.5%) | 2/80 (2.5%) | 0/80 (0.0%) | `eval_v5b_high_real_ratio_80ep/eval_16routes.json` |
| 기존 `stage3_high_v5_b` | **OFF (`--no-safety`)** | 80회 | 54/80 (67.5%) | 25/80 (31.2%) | 1/80 (1.2%) | `eval_v5b_high_real_ratio_nosafety_80ep/eval_16routes.json` |
| **신규 `mcw2_nosafety_final`** | **OFF (`--no-safety`)** | **80회** | **78/80 (97.5%)** | **1/80 (1.2%)** | **1/80 (1.2%)** | `results/mcw_runs/mcw2_nosafety_final/eval_16routes.json` |

- **안전게이트(규칙 기반 강제 차선변경 차단)를 완전히 제거한 상태(`--no-safety`)에서 15,000 vph + 실측 차종 비율(승용 77% / 소형화물 18% / 대형화물 4% / 버스 1%) 80회 평가 기준 완주율 `97.5% (78/80)`, 충돌률 `1.2% (1/80)`, 타임아웃 `1.2% (1/80)`을 달성했습니다.**

### 경로별 상세 성적 (16개 경로 × 5시드 = 80회, `--no-safety`)

| 경로 번호 | 기존 `v5_b` (`--no-safety`) | 신규 `mcw2_nosafety_final` (`--no-safety`) | 비고 |
| :---: | :---: | :---: | :--- |
| **`01`** | 4/5 (충돌 1) | **5/5** | |
| **`02`** | 4/5 (충돌 1) | **5/5** | |
| **`03`** | 2/5 (충돌 3) | **5/5** | |
| **`04`** | 5/5 | **5/5** | |
| **`05`** | 2/5 (충돌 3) | **5/5** | 중앙 51.1m 엇갈림 구간(`170059994`) 통과 |
| **`06`** | 5/5 | **5/5** | |
| **`07`** | 2/5 (충돌 3) | **5/5** | |
| **`08`** | 5/5 | **5/5** | |
| **`09`** | 5/5 | **5/5** | |
| **`10`** | 2/5 (충돌 3) | **5/5** | |
| **`11`** | 4/5 (충돌 1) | **5/5** | |
| **`12`** | 5/5 | **5/5** | |
| **`13`** | 1/5 (충돌 3, 타임아웃 1) | **5/5** | 북측 진입 + 중앙 51.1m 엇갈림 구간 통과 |
| **`14`** | 2/5 (충돌 3) | **4/5** (타임아웃 1) | `seed 40114` 1건만 타임아웃 |
| **`15`** | 1/5 (충돌 4) | **4/5** (충돌 1) | `seed 40115` 1건만 충돌 |
| **`16`** | 5/5 | **5/5** | |
| **합계** | **54/80 (67.5%) · 충돌 25** | **78/80 (97.5%) · 충돌 1 · 타임아웃 1** | **14개 경로 5/5 만점** |

---

## 2. 기존과 동일하게 유지된 사항 (팀 호환성)

1. **관측 공간 (`obs_dim = 47`) 유지**: `ClarityEnv` + `RouteNavigation(horizon=400.0)`의 47차원 관측 구조 및 각 칼럼 스케일(`[-1, 1]`)은 기존과 100% 동일합니다.
2. **행동 공간 (`act_dim = 2`) 및 네트워크 구조 유지**: `HybridActorCritic` (`hidden_sizes=(256, 256)`, `tanh`, 연속 가감속 + 3-way 이산 차선변경) 아키텍처가 그대로 유지되어 기존 평가/데이터 수집 코드와 즉시 호환됩니다.
3. **공용 모듈 무수정**: `env/*`, `algorithms/*`, `utils/networks.py` 등 공용 모듈은 수정하지 않고 `utils/mcw_train.py`와 `utils/mcw_watch.py`에만 변경을 반영했습니다.

---

## 3. 기존 대비 달라진 점 (핵심 개선 내역 4가지)

### ① 안전게이트 기본 비활성화 (`--no-safety` 기본값화)
- `utils/mcw_train.py` 및 `utils/mcw_watch.py`에서 `--safety` 옵션의 기본값을 `True → False`로 변경했습니다.
- 별도 인자를 주지 않아도 항상 `ACTION["lane_change_safety"]["enabled"] = False` 상태로 동작합니다.

### ② 옆 차선 근접/중첩 차량 관측 증발 버그 수정 (`McwEnv._neighbor`)
- **원인 진단**:
  1. 기존 `env/sumo_env.py`의 `_neighbor()`는 `if gap < 0 or gap > self.visibility: return None`으로 처리되어 있었습니다.
  2. 그런데 SUMO `traci.vehicle.getNeighbors()`는 `실제 범퍼 간 거리 - minGap(2.5m)`를 반환하므로, **옆 차선 차량이 실제 거리 `2.5m` 이내로 근접해 있거나 차체가 나란히 겹쳐 있을 때 `gap < 0`이 되어 `None`("옆 차선 앞뒤 50m에 차량 없음, `1.0 / -1.0`")으로 관측에서 증발**하고 있었습니다(기존 모델 게이트 제거 시 발생한 충돌 25건 중 19건의 직접 원인).
  3. 또한 바로 옆 차선(`offset = ±1`)에서는 스폰 직후 차량과 교차부 경계(`via_lane` 및 다음 도로 초입)를 직접 스캔하는 `_scan_lane_neighbors()`가 호출되지 않고 있었습니다.
- **해결**:
  1. `McwEnv._neighbor(offset != 0)`에서 `getNeighbors()`와 `McwEnv._scan_lane_neighbors()`를 모두 조회해 더 가까운 차량을 선택하고, `gap <= 0`인 경우 버리지 않고 **`0.0`("거리 0m = 바로 옆에 차량 있음")으로 클리핑**했습니다.
  2. 옆 차선 차량이 자차와 나란히 겹쳐 있는 경우(`gap <= 0`), 해당 옆 차선 슬롯의 전방(`leader`)과 후방(`follower`) 관측 모두 `0.0`으로 반영해 반대쪽이 `50m 텅 빔`으로 보이던 착시를 제거했습니다.
  3. 합류부 내부(`INTERNAL_MERGE_FOES`)에서도 합류 직후 도로(`out_lane`) 및 도달 시간(ETA) 기반 전방 감지를 보강했습니다.

### ③ 보상 함수 내 횡방향 위험 감점 및 장기 정차 누적 페널티 통합 (`McwEnv.step`)
새로운 보상 옵션을 늘리지 않고 기존 보상 안에 통합했습니다:
1. **`ttc_reward` 확장 (종방향 → 종방향 + 횡방향)**:
   - 기존 종방향(앞차) 안전거리·TTC 감점에 더해, 차선변경 명령(`lc_cmd != 0`) 시 목표 차선 앞/뒤 차량과의 간격이 물리적 위험 임계값(`safe_f = 2.0 + 0.10v`, `safe_r = 2.0 + 0.15v`) 또는 `TTC < 0.8초` 미만일 때 비례 감점(`-0.15`)을 주도록 통합했습니다.
2. **`stall_penalty` 시간 누적 고도화**:
   - 고밀도 교통에서 옆 차선 차량 행렬을 보내주는 정상 대기(`8초 = 40스텝`까지)는 기존 기본 감점(`1.0배`)만 유지합니다.
   - 앞이 비어 있거나(`lead > 25m`) 갈림길 끝(`dist < 10m`) 잘못된 차선에 갇힌 채 `8 ~ 25초` 이상 정차하면 감점이 최대 `2.5배`로 증가하고, **학습 중에만** `30초(150스텝)` 연속 완전 고착(`< 0.5 m/s`) 시 조기 타임아웃(`-15.0`)으로 에피소드를 종료해 할인율($\gamma = 0.99$) 인과관계 소멸과 정지 데이터 오염을 방지합니다. (평가 시에는 기존 `3,000`스텝 기준 그대로 유지)
3. **`prep_reward` (`ProgressReward`) 스케일 보정**:
   - 고밀도에서 차선변경을 포기하지 않도록 목표 차로 방향 1차로 진입 보상을 `+0.1 → +0.3`으로 보정했습니다.

### ④ 안전 간격 판단의 신경망 가중치 내재화 (`distill_safe_policy`, `--distill-passes`)
- **배경**: 이산(`Categorical`) 차선 헤드는 순수 PPO 확률 샘플링(`sample()`) 중 옆 차선 대기 구간(40스텝)에서 무작위로 차선변경을 뽑아 충돌(`-15.0`)을 맞으면 `p_lane_change`가 `0.01` 이하로 붕괴해 `10/16 (62.5%)`에서 멈추는 한계가 있었습니다.
- **해결**: 실행/평가 시에는 안전게이트를 100% 끄고(`--no-safety`), 학습 단계에서 신경망이 직접 주행하며 마주친 47차원 관측(`obs`)마다 *"옆 차 간격이 위험하면 `유지(0)`, 안전한 틈이 열리면 `변경(±1)`"*을 신경망 가중치 자체에 학습시키는 On-policy DAgger(`distill_safe_policy`)를 구현했습니다. (이때 출발 첫 도로가 아닌 중간 짧은 엇갈림 구간 `170059994` 등에서는 `spawn_protect` 15m가 라벨을 막지 않도록 보정하고, 보수적 가중치 `v1`과 적극적 가중치 `v2`를 `0.80 : 0.20`으로 보간해 단일 최종 가중치 `best_model.pt`를 생성했습니다.)

---

## 4. 팀원 배포용 실행 및 재현 명령어

- **80회(`16경로 × 5시드`) `high_real_ratio` `--no-safety` 평가 재현**:
  ```powershell
  python -X utf8 -m utils.mcw_train --stage high_real_ratio --eval-only --eval-episodes 5 --no-safety --lc-penalty 0.01 --lane-keep-bias 0.5 --timeout-penalty 15.0 --stall-penalty 0.08 --resume results/mcw_runs/mcw2_nosafety_final/best_model.pt --name eval_mcw2_nosafety_final_80ep
  ```
- **SUMO-GUI 주행 재생 확인 (`--no-safety` 및 신규 모델이 기본값으로 설정됨)**:
  ```powershell
  python -X utf8 -m utils.mcw_watch --route route_05 --seed 40005
  ```
- **단위 테스트**:
  ```powershell
  python -m unittest discover -s tests -v
  ```

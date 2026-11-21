# 퇴계원IC 커리큘럼 PPO 최종 학습 및 다중 시드 검증 리포트 (MCW)

> 작성일: 2026-11-16  
> 브랜치 / 러너: `mcw` / `utils/mcw_train.py` (47차원 `ClarityEnv` + `RouteNavigation(horizon=400.0)`)  
> 최종 선정 체크포인트: `results/mcw_runs/stage3_high_v5_b/best_model.pt`  
> 목표 기준: 완주율 **≥ 95%**, 충돌률 **< 5%** (16개 경로 × 5시드 = 80회 다중 시드 평가 기준)

---

## 1. 최종 검증 성적 요약

| 평가 조건 | 시행 수 | 완주 (Arrival) | 충돌 (Collision) | 타임아웃 (Timeout) | 결과 파일 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Stage 1 (`none`, 무교통)** | 16회 | **16/16 (100.0%)** | **0 (0.0%)** | 0 (0.0%) | `stage1_none/eval_final.json` |
| **Stage 2 (`low`, ~3,000 vph)** | 16회 | **14/16 (87.5%)** | 2 (12.5%) | 0 (0.0%) | `stage2_low/eval_51200.json` |
| **Stage 3 (`high`, 15,000 vph)** | **80회** | **74/80 (92.5%)** | **0 (0.0%)** | 6 (7.5%) | `eval_v5b_blindspot_v3_80ep/eval_16routes.json` |
| **`real_ratio` (실측 차종 비율, 0.5배 7,500 vph)** | **80회** | **77/80 (96.2%)** | **0 (0.0%)** | 3 (3.8%) | `eval_v5b_real_ratio_80ep/eval_16routes.json` |
| **`high_real_ratio` (15,000 vph + 실측 차종 비율)** | **80회** | **78/80 (97.5%)** | **2 (2.5%)** | **0 (0.0%)** | `eval_v5b_high_real_ratio_80ep/eval_16routes.json` |

- **회의 기준 15,000 vph + 2025년 실측 차종 비율(승용 77% / 소형화물 18% / 대형화물 4% / 버스 1%) 동시 조건(`high_real_ratio`)에서 80회 기준 완주율 `97.5% (78/80)`, 충돌률 `2.5% (2/80)` (< 5% 기준 충족), 타임아웃 `0건 (0.0%)`을 달성했습니다.**
- 기존 HV 비율(승용 95% / 버스 5%)의 `15,000 vph (high)` 극한 조건에서도 **충돌 `0건 (0.0%)`, 완주 `92.5% (74/80)`**를 기록했습니다.

---

## 2. 단계별 핵심 개선 및 원인 해결 내역

### ① 경로 기준 차로 연결성 + 400m 사전 차선 준비 (`Stage 1: 100%`)
- **변경**: `_lane_connectivity`가 임의의 출구가 아니라 **실제 `ego` 경로의 다음 도로(`path[idx + 1]`)와 연결된 차로만 `1.0`**을 주도록 수정하고, `ProgressReward` + `horizon=400.0m`로 분기점 전 사전 차선 준비를 학습.
- **효과**: 무교통 16개 경로 `100.0% (16/16)` 완주.

### ② 타임아웃 감점 + 무방해 정지 페널티 + 차선유지 바이어스 절충 (`high: 37.5% → 87.5%`)
- **발견한 문제**: 고밀도 환경 초기에는 타임아웃(`cut=True`) 감점이 `0`점이었고 `0 m/s` 정지에 대한 즉각 감점도 없어, 에이전트가 충돌(`-15.0`)을 피하려고 아예 `0 m/s`로 멈춰 서 버리는 국소 최적해에 빠짐(당시 타임아웃 최대 `12/16`).
- **변경**: `--timeout-penalty 15.0`, 무방해 저속/정지(`gap > 25m` 또는 앞차 없음 & `speed < 3.0 m/s`) 시 `--stall-penalty 0.08`, `--lc-penalty 0.01`, `--lane-keep-bias 0.5`.
- **효과**: 15,000 vph 80회 평가 완주율이 `82.5% → 87.5%`로 상승.

### ③ 안전게이트 현실화 (`min_front/rear_gap: 5.0 → 3.5m`, `rear_tau: 0.5 → 0.35s`)
- **발견한 문제**: `170059994` (51.1m 엇갈림 구간) 등에서 차선 변경을 24회 시도하고도 보수적 게이트에 전부 막혀 타임아웃(`05`번 `1/5`).
- **효과**: `05`번 타임아웃 해소.

### ④ 도로 경계면·합류부 사각지대 패치 (`high` 충돌 `7.5% → 0.0%`, 완주 `92.5%`)
- **발견한 문제**: 충돌 6건(80회) 전수 진단 결과,
  1. 도로 끝에서 옆 차가 교차부(`:junction`)로 반 발짝 진입하면 `_scan_lane_neighbors`에서 사라지는 **증발 버그**(`02, 05, 06, 13`번 `side/junction` 충돌),
  2. 동쪽 1차로 램프(`169728849`) 등 지퍼 합류부에서 진입 직전까지 본선 차량이 `getLeader`에 잡히지 않는 **합류 사각지대**(`01, 02`번 추돌)가 원인임을 확인.
- **변경**: `_scan_lane_neighbors`를 `교차부 + 다음 도로 첫 5m`(현재 도로 끝 `35m` 이내일 때만)까지 확장하고, `MERGE_FOES` / `INTERNAL_MERGE_FOES`로 합류 상대 차량을 전방 `leader`에 반영.
- **효과**: 재학습 없이 `high` 80회 평가에서 **충돌 `6건 → 0건 (0.0%)`**, 완주 `87.5% → 92.5%` 달성.

---

## 3. `high_real_ratio` & `high` 경로별 결과 (각 5회씩)

| 경로 번호 | `high` (15,000 vph) | `real_ratio` (7,500 vph 실측비율) | `high_real_ratio` (15,000 vph 실측비율) |
| :---: | :---: | :---: | :---: |
| **`01`** | 5/5 | 5/5 | 4/5 (충돌 1) |
| **`02`** | 5/5 | 5/5 | 4/5 (충돌 1) |
| **`03`** | 5/5 | 5/5 | **5/5** |
| **`04`** | 5/5 | 5/5 | **5/5** |
| **`05`** | 5/5 | 5/5 | **5/5** |
| **`06`** | 5/5 | 5/5 | **5/5** |
| **`07`** | 2/5 (타임아웃 3) | 5/5 | **5/5** |
| **`08`** | 5/5 | 5/5 | **5/5** |
| **`09`** | 5/5 | 5/5 | **5/5** |
| **`10`** | 5/5 | 5/5 | **5/5** |
| **`11`** | 5/5 | 5/5 | **5/5** |
| **`12`** | 5/5 | 5/5 | **5/5** |
| **`13`** | 3/5 (타임아웃 2) | 5/5 | **5/5** |
| **`14`** | 4/5 (타임아웃 1) | 2/5 (타임아웃 3) | **5/5** |
| **`15`** | 5/5 | 5/5 | **5/5** |
| **`16`** | 5/5 | 5/5 | **5/5** |
| **합계** | **74/80 (92.5%) · 충돌 0** | **77/80 (96.2%) · 충돌 0** | **78/80 (97.5%) · 충돌 2** |

---

## 4. 검증 및 재현 명령어

- **모델/결과 압축 풀기** (저장소 최상위에서 실행):
  ```powershell
  Expand-Archive -LiteralPath results/mcw_runs/mcw-models-20261116.zip -DestinationPath .
  ```
- **단위 테스트**: `C:\Users\문시원\AppData\Local\Programs\Python\Python39\python.exe -m unittest discover -s tests -v` (`Ran 6 tests / OK`)
- **동일 `high_real_ratio` 조건 `gap-lane-22` 교차 검증** (`results/mcw_runs/eval_kyh_gap_lane_22_high_real_ratio_80ep/eval_16routes.json`): **`80/80 (100.0%)`**, 충돌 `0 (0.0%)`, 타임아웃 `0`
- **`high_real_ratio` (15,000 vph + 실측 차종 비율) 80회 재현**:
  ```powershell
  C:\Users\문시원\AppData\Local\Programs\Python\Python39\python.exe -X utf8 -m utils.mcw_train --stage high_real_ratio --eval-only --eval-episodes 5 --lc-penalty 0.01 --lane-keep-bias 0.5 --timeout-penalty 15.0 --stall-penalty 0.08 --min-front-gap 3.5 --min-rear-gap 3.5 --rear-tau 0.35 --resume results/mcw_runs/stage3_high_v5_b/best_model.pt --name eval_v5b_high_real_ratio_80ep
  ```
- **SUMO-GUI 주행 재생 확인**:
  ```powershell
  C:\Users\문시원\AppData\Local\Programs\Python\Python39\python.exe -X utf8 -m utils.mcw_watch --route route_05 --seed 40005
  ```

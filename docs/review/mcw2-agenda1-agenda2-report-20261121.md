# 퇴계원IC 안건 1·2 적용 검증 및 80회 다중시드 리포트 (`mcw2`)

> 작성일: 2026-11-21  
> 브랜치 / 러너: `mcw2` / `utils/mcw_train.py`, `utils/mcw_blend.py` (`47차원` 호환 `McwEnv`)  
> 안전게이트 설정: **`--no-safety` (`ACTION["lane_change_safety"]["enabled"] = False`)**  
> 목표 기준: 완주율 **≥ 95%**, 충돌률 **< 5%** (`high_real_ratio` 16개 경로 × 5시드 = 80회)

---

## 1. 최종 성적 비교 (`high_real_ratio`, 15,000 vph + 실측 차종 비율)

| 단계 / 체크포인트 | 적용 조건 | 시행 수 | 완주 (`Arrival`) | 충돌 (`Collision`) | 타임아웃 (`Timeout`) | 결과 파일 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| 기존 기준 (`mcw2_nosafety_final`) | `50m`, 노이즈 OFF, `--no-safety` | 80회 | 78/80 (97.5%) | 1/80 (1.2%) | 1/80 (1.2%) | `results/mcw_runs/mcw2_nosafety_final/eval_16routes.json` |
| **안건 1 (`mcw2_120m_noise_final`)** | **`120m`, `--obs-noise`, `--no-safety`** | **80회** | **77/80 (96.2%)** | **3/80 (3.8%)** | **0/80 (0.0%)** | `results/mcw_runs/eval_mcw2_120m_noise_final_80ep/eval_16routes.json` |
| **안건 2 (`mcw2_agenda2_final`)** | **`120m`, `--obs-noise`, `--no-safety`, `--agenda2`** | **80회** | **78/80 (97.5%)** | **2/80 (2.5%)** | **0/80 (0.0%)** | `results/mcw_runs/eval_mcw2_agenda2_final_80ep/eval_16routes.json` |

- **안건 1 실패 3건**: `route_02 (seed 40202, collision)`, `route_07 (seed 40207, 40407, collision)` (`14/16` 경로 `5/5`, 타임아웃 `0`)
- **안건 2 실패 2건**: `route_05 (seed 40305, collision)`, `route_13 (seed 40313, collision)` (`14/16` 경로 `5/5`, 타임아웃 `0`)

---

## 2. 안건별 변경 사항

### ① 안건 1: 감지 범위 `120m` 확장 + 거리 비례 가우시안 노이즈
- `--visibility` 기본값 `50.0 → 120.0` 확장
- `--obs-noise` (`McwEnv._get_obs`) 적용: 감지된 전·후방 차량에 거리 비율(`frac = gap / visibility`)에 비례한 가우시안 노이즈 추가
  - 거리 표준편차: `noise_gap_base(0.2) + noise_gap_slope(3.6) * frac` (m)
  - 속도 표준편차: `noise_vel_base(0.15) + noise_vel_slope(1.35) * frac` (m/s)
- 미감지 슬롯(`±1.0`)은 센티넬 값 그대로 유지

### ② 안건 2 (`--agenda2`): 목표 차로 지시 힌트 제거 + Multi-hop 경로 연결성
- **제거 (`0.0` 마스킹, `47차원` 호환 유지):**
  - `obs[31]`: 현재 목표 차로 상대 오프셋 (`current_targets` offset)
  - `obs[32]`: `400m` 선행 제약까지 거리
  - `obs[33]`: 선행 준비 차로 상대 오프셋 (`prepare_targets` offset)
  - `obs[37:39]`: 목표/선행 차로 안내 유효 플래그
  - `obs[39:47]`: 두 번째 제약 거리 및 6차로 이진 마스크
- **보완 (`McwEnv._lane_connectivity`, `obs[21:26]`):**
  - 기존 *"바로 다음 엣지 1개(`path[idx + 1]`)만 확인"*에서 **`visibility(120m)` 이내 미래 경로 링크(`links`)를 따라가는 Multi-hop 연결성**으로 확장해, `67m`·`51m` 등 짧은 다단 분기 구간 진입 전에도 차로 끊김을 인지할 수 있도록 보완했습니다.

---

## 3. 계보 · 체크포인트 · 블렌딩 · 재현 커맨드 (SHA-256)

> **전제 명시**: 안건 1·2 모델은 각각 직전 단계 모델(`mcw2_nosafety_final` → `mcw2_120m_noise_final` → `mcw2_agenda2_final`)에서 `--resume` 전이 학습 및 `DAgger/PPO`를 거쳐 생성되었으며, 보상 함수와 `--no-safety` 설정은 변경 없이 유지했습니다.

| 단계 | 체크포인트 경로 | SHA-256 (앞 12자리) | 비고 |
| :--- | :--- | :---: | :--- |
| **안건 1 DAgger** | `results/mcw_runs/mcw2_120m_noise_dagger/best_model.pt` | `47f189e0349c` | `mcw2_nosafety_final`에서 4-pass DAgger |
| **안건 1 최종 (`96.2%`)** | `results/mcw_runs/mcw2_120m_noise_final/best_model.pt` | `d0d3981cbb39` | `alpha=0.45` (`0.55·nosafety_final + 0.45·120m_noise_dagger`) |
| **안건 2 `--no-safety` PPO** | `results/mcw_runs/mcw2_agenda2_ppo_80k/best_model.pt` | `8acab17478cd` | `51,200` step (`75/80 = 93.8%`, 충돌 `5`, 타임아웃 `0`) |
| **안건 2 저학습률 DAgger v2** | `results/mcw_runs/mcw2_agenda2_dagger_v2/best_model.pt` | `f2126af64a90` | `51.2k`에서 `3-pass`, `--distill-lr 8e-5`, Pass 1 (`15/16`, 충돌 `0`) |
| **안건 2 최종 (`97.5%`)** | `results/mcw_runs/mcw2_agenda2_final/best_model.pt` | `a4739cc53a1c` | `alpha=0.50` (`0.50·ppo_80k + 0.50·dagger_v2`) |

### 주요 재현 커맨드 (Python 3.9)
```bash
# 1) 안건 2 최종 블렌드 검증
python utils/mcw_blend.py \
  --v1 results/mcw_runs/mcw2_agenda2_ppo_80k/best_model.pt \
  --v2 results/mcw_runs/mcw2_agenda2_dagger_v2/best_model.pt \
  --alpha 0.50 \
  --out results/mcw_runs/mcw2_agenda2_final/best_model.pt \
  --verify-only

# 2) 안건 2 최종 80에피소드 평가
python -m utils.mcw_train --stage high_real_ratio --no-safety \
  --visibility 120.0 --obs-noise --agenda2 \
  --resume results/mcw_runs/mcw2_agenda2_final/best_model.pt \
  --eval-only --eval-episodes 5 --name eval_mcw2_agenda2_final_80ep

# 3) 단위 테스트
python -m unittest discover -s tests -v
```

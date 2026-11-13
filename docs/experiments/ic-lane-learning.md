# 차선 탐험 감소와 경로 차로 보상 독립 비교

## 고정 조건과 설계

기존 관측(47차원 중 추가 10차원은 0), 무교통 16경로, PPO 구조·감마 0.99·학습률 0.0003·80만 스텝·seed 11/22/33·출발 조건을 유지한다. 기존 실험의 초기 가중치와 일치하는지 확인한다. 강제 행동 보정은 사용하지 않는다.

- 기준: 완료된 `navigation_clarity_v1/runs/baseline-*`를 보존하고 같은 중간 단계 정책을 재평가한다. 중복 학습하지 않는다.
- 탐험 감소: 40만 단계까지 차선 엔트로피 계수 0.01, 이후 80만까지 선형으로 0으로 감소. 보상은 원래 그대로.
- 목적지 차로 보상: 탐험 계수는 0.01 유지. 분기 100m 이내에서 안내 계산이 가능하고 같은 도로 구간에서 실제 차로 변경으로 목표 차로까지의 차로 수가 줄어들면 한 차로당 +0.1. 같은 에피소드·도로 구간·목표 차로 집합에서 동일한 접근 단계는 한 번만 지급한다. 정지·차로 유지·좌우 반복으로 중복 보상하지 않는다. 변경 명령을 대신 내리지 않는다. 계수는 첫 비교용 가설이며 최적값이 아니다.

두 변경은 섞지 않는다. 각각 3 seed, 총 6개 독립 학습을 최대 6개 프로세스, 프로세스당 PyTorch 1스레드로 병렬 실행한다. 각 프로세스는 자기 평가 중 학습을 잠시 멈추므로 동시에 SUMO가 무제한 증가하지 않는다.

## 구현 및 검증 순서

1. 새 실험 전용 모듈에 보상 장부와 탐험 스케줄을 구현한다. 기존 학습·환경 코드는 변경하지 않는다.
2. 스케줄 경계, 유지·멀어짐·반복 이동·안내 불가·100m 밖 보상 0, 첫 접근 보상만 지급을 검증한다.
3. 두 조건 2048스텝 실제 학습으로 관측 크기·행동 무보정·로그·초기 가중치 동일성을 검증한다.
4. 6개 작업을 시작한다. 2만 단계 간격 저장, 약 10만 단계마다 기존과 동일한 62개 출발 조건으로 결정론적 평가한다. 학습 중 SUMO 연결과 난수 상태에 영향을 주지 않도록 평가는 별도 프로세스에서 수행한다.
5. 기준도 같은 10만 단계 간격으로 평가한다. 경로별 완주·충돌·시간 초과, 최고/최종 모델, 성공 후 실패 전환을 기록한다. 동일 검증 집합에서 고른 최고 성능은 독립 시험 성능으로 주장하지 않는다.

원본 기준 코드/맵 해시, 초기 가중치 해시, 현재 커밋, 실제 계수와 보상 누적량은 각 실행 manifest와 TensorBoard에 보존한다. 결과 원본은 `results/lane_learning_v1/`에 로컬 저장한다. Git에는 코드와 요약만 기록한다. 완주율 95%·충돌률 5% 목표 달성 여부는 이후 별도 미사용 출발 조건으로 확인한다.

## 추가 조합 실험

탐험 감소와 목적지 차로 보상을 함께 적용하는 `combined` 조건을 추가한다. 앞선 독립 실험은 보존한다. seed 11/22/33을 같은 초기 가중치에서 각각 80만 스텝 새로 학습하며 세 작업을 병렬 실행한다. 최고 중간 모델에서 이어 학습하지 않는다.

- 탐험: 40만까지 0.01, 이후 80만까지 선형 감소하여 0 도달.
- 보상: 단독 실험과 동일한 100m·한 차로 접근당 +0.1·중복 지급 방지.
- 나머지 관측·도로·무교통·학습률·감마·행동 제약은 동일, 강제 보정 없음.
- 약 10만마다 동일 62개 조건, 3 seed 합계 186회로 평가한다. 2만 간격 정책도 보존한다.
- 최고 성능 최초 도달 단계, 이후 유지 구간, 최종 하락 및 seed 편차를 비교한다. 100%는 해당 평가 집합의 상한이며 포화·수렴의 확정 증거가 아니다. 최종 일반화는 별도 출발 조건에서 검증해야 한다.
- 실행: `python -m utils.train_lane_learning --combined`. 상태 `results/lane_learning_v1/combined-status.json`, 모델 `runs/combined-*`, 평가 `evaluations/combined-*`.

## 실행 결과

각 셀은 동일한 62개 출발 조건의 완주 수다. 기준과 두 변경 조건 모두 같은 평가를 사용한다.

| 조건 / seed | 단계 | 완주 | 충돌 | 시간 초과 |
|---|---:|---:|---:|---:|
| baseline-11 | 100352 | 57/62 | 0 | 5 |
| baseline-11 | 200704 | 42/62 | 0 | 20 |
| baseline-11 | 301056 | 59/62 | 0 | 3 |
| baseline-11 | 401408 | 62/62 | 0 | 0 |
| baseline-11 | 501760 | 56/62 | 0 | 6 |
| baseline-11 | 600064 | 50/62 | 0 | 12 |
| baseline-11 | 700416 | 62/62 | 0 | 0 |
| baseline-11 | 800000 | 62/62 | 0 | 0 |
| baseline-22 | 100352 | 52/62 | 0 | 10 |
| baseline-22 | 200704 | 62/62 | 0 | 0 |
| baseline-22 | 301056 | 62/62 | 0 | 0 |
| baseline-22 | 401408 | 47/62 | 0 | 15 |
| baseline-22 | 501760 | 62/62 | 0 | 0 |
| baseline-22 | 600064 | 62/62 | 0 | 0 |
| baseline-22 | 700416 | 59/62 | 0 | 3 |
| baseline-22 | 800000 | 59/62 | 0 | 3 |
| baseline-33 | 100352 | 54/62 | 0 | 8 |
| baseline-33 | 200704 | 62/62 | 0 | 0 |
| baseline-33 | 301056 | 62/62 | 0 | 0 |
| baseline-33 | 401408 | 59/62 | 0 | 3 |
| baseline-33 | 501760 | 52/62 | 0 | 10 |
| baseline-33 | 600064 | 62/62 | 0 | 0 |
| baseline-33 | 700416 | 62/62 | 0 | 0 |
| baseline-33 | 800000 | 52/62 | 0 | 10 |
| combined-11 | 100352 | 62/62 | 0 | 0 |
| combined-11 | 200704 | 58/62 | 0 | 4 |
| combined-11 | 301056 | 62/62 | 0 | 0 |
| combined-11 | 401408 | 62/62 | 0 | 0 |
| combined-11 | 501760 | 62/62 | 0 | 0 |
| combined-11 | 600064 | 62/62 | 0 | 0 |
| combined-11 | 700416 | 59/62 | 0 | 3 |
| combined-11 | 800000 | 62/62 | 0 | 0 |
| combined-22 | 100352 | 62/62 | 0 | 0 |
| combined-22 | 200704 | 59/62 | 0 | 3 |
| combined-22 | 301056 | 61/62 | 0 | 1 |
| combined-22 | 401408 | 62/62 | 0 | 0 |
| combined-22 | 501760 | 55/62 | 0 | 7 |
| combined-22 | 600064 | 62/62 | 0 | 0 |
| combined-22 | 700416 | 62/62 | 0 | 0 |
| combined-22 | 800000 | 62/62 | 0 | 0 |
| combined-33 | 100352 | 55/62 | 0 | 7 |
| combined-33 | 200704 | 62/62 | 0 | 0 |
| combined-33 | 301056 | 62/62 | 0 | 0 |
| combined-33 | 401408 | 44/62 | 0 | 18 |
| combined-33 | 501760 | 62/62 | 0 | 0 |
| combined-33 | 600064 | 62/62 | 0 | 0 |
| combined-33 | 700416 | 41/62 | 0 | 21 |
| combined-33 | 800000 | 56/62 | 0 | 6 |
| entropy-11 | 100352 | 57/62 | 0 | 5 |
| entropy-11 | 200704 | 42/62 | 0 | 20 |
| entropy-11 | 301056 | 59/62 | 0 | 3 |
| entropy-11 | 401408 | 62/62 | 0 | 0 |
| entropy-11 | 501760 | 62/62 | 0 | 0 |
| entropy-11 | 600064 | 62/62 | 0 | 0 |
| entropy-11 | 700416 | 62/62 | 0 | 0 |
| entropy-11 | 800000 | 56/62 | 0 | 6 |
| entropy-22 | 100352 | 52/62 | 0 | 10 |
| entropy-22 | 200704 | 62/62 | 0 | 0 |
| entropy-22 | 301056 | 62/62 | 0 | 0 |
| entropy-22 | 401408 | 47/62 | 0 | 15 |
| entropy-22 | 501760 | 62/62 | 0 | 0 |
| entropy-22 | 600064 | 62/62 | 0 | 0 |
| entropy-22 | 700416 | 62/62 | 0 | 0 |
| entropy-22 | 800000 | 62/62 | 0 | 0 |
| entropy-33 | 100352 | 54/62 | 0 | 8 |
| entropy-33 | 200704 | 62/62 | 0 | 0 |
| entropy-33 | 301056 | 62/62 | 0 | 0 |
| entropy-33 | 401408 | 56/62 | 0 | 6 |
| entropy-33 | 501760 | 62/62 | 0 | 0 |
| entropy-33 | 600064 | 62/62 | 0 | 0 |
| entropy-33 | 700416 | 59/62 | 0 | 3 |
| entropy-33 | 800000 | 43/62 | 0 | 19 |
| reward-11 | 100352 | 62/62 | 0 | 0 |
| reward-11 | 200704 | 58/62 | 0 | 4 |
| reward-11 | 301056 | 62/62 | 0 | 0 |
| reward-11 | 401408 | 62/62 | 0 | 0 |
| reward-11 | 501760 | 62/62 | 0 | 0 |
| reward-11 | 600064 | 62/62 | 0 | 0 |
| reward-11 | 700416 | 44/62 | 0 | 18 |
| reward-11 | 800000 | 59/62 | 0 | 3 |
| reward-22 | 100352 | 62/62 | 0 | 0 |
| reward-22 | 200704 | 59/62 | 0 | 3 |
| reward-22 | 301056 | 61/62 | 0 | 1 |
| reward-22 | 401408 | 62/62 | 0 | 0 |
| reward-22 | 501760 | 62/62 | 0 | 0 |
| reward-22 | 600064 | 62/62 | 0 | 0 |
| reward-22 | 700416 | 62/62 | 0 | 0 |
| reward-22 | 800000 | 62/62 | 0 | 0 |
| reward-33 | 100352 | 55/62 | 0 | 7 |
| reward-33 | 200704 | 62/62 | 0 | 0 |
| reward-33 | 301056 | 62/62 | 0 | 0 |
| reward-33 | 401408 | 44/62 | 0 | 18 |
| reward-33 | 501760 | 58/62 | 0 | 4 |
| reward-33 | 600064 | 62/62 | 0 | 0 |
| reward-33 | 700416 | 62/62 | 0 | 0 |
| reward-33 | 800000 | 38/62 | 0 | 24 |

### 단계별 완주율 (3 seed 합계)

| 단계 | 기존 | 탐험 감소 | 차로 보상 | 조합 |
|---:|---:|---:|---:|---:|
| 100352 | 87.63% | 87.63% | 96.24% | 96.24% |
| 200704 | 89.25% | 89.25% | 96.24% | 96.24% |
| 301056 | 98.39% | 98.39% | 99.46% | 99.46% |
| 401408 | 90.32% | 88.71% | 90.32% | 90.32% |
| 501760 | 91.40% | 100.00% | 97.85% | 96.24% |
| 600064 | 93.55% | 100.00% | 100.00% | 100.00% |
| 700416 | 98.39% | 98.39% | 90.32% | 87.10% |
| 800000 | 93.01% | 86.56% | 85.48% | 96.77% |

### 변화 추적

| 조건 / seed | 현재 단계 | 기준 대비 완주율 차이 | 관측 최고 단계 | 직전 대비 성공→실패 / 실패→성공 |
|---|---:|---:|---:|---:|
| baseline-11 | 800000 | +0.00%p | 401408 (62/62) | 0 / 0 |
| baseline-22 | 800000 | +0.00%p | 200704 (62/62) | 0 / 0 |
| baseline-33 | 800000 | +0.00%p | 200704 (62/62) | 10 / 0 |
| combined-11 | 800000 | +0.00%p | 100352 (62/62) | 0 / 3 |
| combined-22 | 800000 | +4.84%p | 100352 (62/62) | 0 / 0 |
| combined-33 | 800000 | +6.45%p | 200704 (62/62) | 0 / 15 |
| entropy-11 | 800000 | -9.68%p | 401408 (62/62) | 6 / 0 |
| entropy-22 | 800000 | +4.84%p | 200704 (62/62) | 0 / 0 |
| entropy-33 | 800000 | -14.52%p | 200704 (62/62) | 16 / 0 |
| reward-11 | 800000 | -4.84%p | 100352 (62/62) | 3 / 18 |
| reward-22 | 800000 | +4.84%p | 100352 (62/62) | 0 / 0 |
| reward-33 | 800000 | -22.58%p | 200704 (62/62) | 24 / 0 |

### 최신 경로별 완주

| 조건 / seed | 경로 | 완주 / 사례 |
|---|---|---:|
| baseline-11 | route_01 | 3/3 |
| baseline-11 | route_02 | 3/3 |
| baseline-11 | route_03 | 4/4 |
| baseline-11 | route_04 | 4/4 |
| baseline-11 | route_05 | 4/4 |
| baseline-11 | route_06 | 4/4 |
| baseline-11 | route_07 | 4/4 |
| baseline-11 | route_08 | 4/4 |
| baseline-11 | route_09 | 4/4 |
| baseline-11 | route_10 | 4/4 |
| baseline-11 | route_11 | 4/4 |
| baseline-11 | route_12 | 4/4 |
| baseline-11 | route_13 | 4/4 |
| baseline-11 | route_14 | 4/4 |
| baseline-11 | route_15 | 4/4 |
| baseline-11 | route_16 | 4/4 |
| baseline-22 | route_01 | 3/3 |
| baseline-22 | route_02 | 3/3 |
| baseline-22 | route_03 | 4/4 |
| baseline-22 | route_04 | 4/4 |
| baseline-22 | route_05 | 4/4 |
| baseline-22 | route_06 | 4/4 |
| baseline-22 | route_07 | 4/4 |
| baseline-22 | route_08 | 4/4 |
| baseline-22 | route_09 | 4/4 |
| baseline-22 | route_10 | 4/4 |
| baseline-22 | route_11 | 4/4 |
| baseline-22 | route_12 | 4/4 |
| baseline-22 | route_13 | 3/4 |
| baseline-22 | route_14 | 3/4 |
| baseline-22 | route_15 | 3/4 |
| baseline-22 | route_16 | 4/4 |
| baseline-33 | route_01 | 3/3 |
| baseline-33 | route_02 | 0/3 |
| baseline-33 | route_03 | 4/4 |
| baseline-33 | route_04 | 4/4 |
| baseline-33 | route_05 | 4/4 |
| baseline-33 | route_06 | 4/4 |
| baseline-33 | route_07 | 4/4 |
| baseline-33 | route_08 | 0/4 |
| baseline-33 | route_09 | 4/4 |
| baseline-33 | route_10 | 4/4 |
| baseline-33 | route_11 | 4/4 |
| baseline-33 | route_12 | 4/4 |
| baseline-33 | route_13 | 4/4 |
| baseline-33 | route_14 | 4/4 |
| baseline-33 | route_15 | 4/4 |
| baseline-33 | route_16 | 1/4 |
| combined-11 | route_01 | 3/3 |
| combined-11 | route_02 | 3/3 |
| combined-11 | route_03 | 4/4 |
| combined-11 | route_04 | 4/4 |
| combined-11 | route_05 | 4/4 |
| combined-11 | route_06 | 4/4 |
| combined-11 | route_07 | 4/4 |
| combined-11 | route_08 | 4/4 |
| combined-11 | route_09 | 4/4 |
| combined-11 | route_10 | 4/4 |
| combined-11 | route_11 | 4/4 |
| combined-11 | route_12 | 4/4 |
| combined-11 | route_13 | 4/4 |
| combined-11 | route_14 | 4/4 |
| combined-11 | route_15 | 4/4 |
| combined-11 | route_16 | 4/4 |
| combined-22 | route_01 | 3/3 |
| combined-22 | route_02 | 3/3 |
| combined-22 | route_03 | 4/4 |
| combined-22 | route_04 | 4/4 |
| combined-22 | route_05 | 4/4 |
| combined-22 | route_06 | 4/4 |
| combined-22 | route_07 | 4/4 |
| combined-22 | route_08 | 4/4 |
| combined-22 | route_09 | 4/4 |
| combined-22 | route_10 | 4/4 |
| combined-22 | route_11 | 4/4 |
| combined-22 | route_12 | 4/4 |
| combined-22 | route_13 | 4/4 |
| combined-22 | route_14 | 4/4 |
| combined-22 | route_15 | 4/4 |
| combined-22 | route_16 | 4/4 |
| combined-33 | route_01 | 3/3 |
| combined-33 | route_02 | 3/3 |
| combined-33 | route_03 | 2/4 |
| combined-33 | route_04 | 2/4 |
| combined-33 | route_05 | 2/4 |
| combined-33 | route_06 | 4/4 |
| combined-33 | route_07 | 4/4 |
| combined-33 | route_08 | 4/4 |
| combined-33 | route_09 | 4/4 |
| combined-33 | route_10 | 4/4 |
| combined-33 | route_11 | 4/4 |
| combined-33 | route_12 | 4/4 |
| combined-33 | route_13 | 4/4 |
| combined-33 | route_14 | 4/4 |
| combined-33 | route_15 | 4/4 |
| combined-33 | route_16 | 4/4 |
| entropy-11 | route_01 | 3/3 |
| entropy-11 | route_02 | 3/3 |
| entropy-11 | route_03 | 3/4 |
| entropy-11 | route_04 | 3/4 |
| entropy-11 | route_05 | 3/4 |
| entropy-11 | route_06 | 4/4 |
| entropy-11 | route_07 | 4/4 |
| entropy-11 | route_08 | 4/4 |
| entropy-11 | route_09 | 4/4 |
| entropy-11 | route_10 | 4/4 |
| entropy-11 | route_11 | 4/4 |
| entropy-11 | route_12 | 4/4 |
| entropy-11 | route_13 | 3/4 |
| entropy-11 | route_14 | 3/4 |
| entropy-11 | route_15 | 3/4 |
| entropy-11 | route_16 | 4/4 |
| entropy-22 | route_01 | 3/3 |
| entropy-22 | route_02 | 3/3 |
| entropy-22 | route_03 | 4/4 |
| entropy-22 | route_04 | 4/4 |
| entropy-22 | route_05 | 4/4 |
| entropy-22 | route_06 | 4/4 |
| entropy-22 | route_07 | 4/4 |
| entropy-22 | route_08 | 4/4 |
| entropy-22 | route_09 | 4/4 |
| entropy-22 | route_10 | 4/4 |
| entropy-22 | route_11 | 4/4 |
| entropy-22 | route_12 | 4/4 |
| entropy-22 | route_13 | 4/4 |
| entropy-22 | route_14 | 4/4 |
| entropy-22 | route_15 | 4/4 |
| entropy-22 | route_16 | 4/4 |
| entropy-33 | route_01 | 3/3 |
| entropy-33 | route_02 | 3/3 |
| entropy-33 | route_03 | 0/4 |
| entropy-33 | route_04 | 0/4 |
| entropy-33 | route_05 | 0/4 |
| entropy-33 | route_06 | 4/4 |
| entropy-33 | route_07 | 4/4 |
| entropy-33 | route_08 | 4/4 |
| entropy-33 | route_09 | 4/4 |
| entropy-33 | route_10 | 4/4 |
| entropy-33 | route_11 | 0/4 |
| entropy-33 | route_12 | 4/4 |
| entropy-33 | route_13 | 3/4 |
| entropy-33 | route_14 | 3/4 |
| entropy-33 | route_15 | 3/4 |
| entropy-33 | route_16 | 4/4 |
| reward-11 | route_01 | 3/3 |
| reward-11 | route_02 | 0/3 |
| reward-11 | route_03 | 4/4 |
| reward-11 | route_04 | 4/4 |
| reward-11 | route_05 | 4/4 |
| reward-11 | route_06 | 4/4 |
| reward-11 | route_07 | 4/4 |
| reward-11 | route_08 | 4/4 |
| reward-11 | route_09 | 4/4 |
| reward-11 | route_10 | 4/4 |
| reward-11 | route_11 | 4/4 |
| reward-11 | route_12 | 4/4 |
| reward-11 | route_13 | 4/4 |
| reward-11 | route_14 | 4/4 |
| reward-11 | route_15 | 4/4 |
| reward-11 | route_16 | 4/4 |
| reward-22 | route_01 | 3/3 |
| reward-22 | route_02 | 3/3 |
| reward-22 | route_03 | 4/4 |
| reward-22 | route_04 | 4/4 |
| reward-22 | route_05 | 4/4 |
| reward-22 | route_06 | 4/4 |
| reward-22 | route_07 | 4/4 |
| reward-22 | route_08 | 4/4 |
| reward-22 | route_09 | 4/4 |
| reward-22 | route_10 | 4/4 |
| reward-22 | route_11 | 4/4 |
| reward-22 | route_12 | 4/4 |
| reward-22 | route_13 | 4/4 |
| reward-22 | route_14 | 4/4 |
| reward-22 | route_15 | 4/4 |
| reward-22 | route_16 | 4/4 |
| reward-33 | route_01 | 3/3 |
| reward-33 | route_02 | 3/3 |
| reward-33 | route_03 | 0/4 |
| reward-33 | route_04 | 0/4 |
| reward-33 | route_05 | 0/4 |
| reward-33 | route_06 | 4/4 |
| reward-33 | route_07 | 4/4 |
| reward-33 | route_08 | 4/4 |
| reward-33 | route_09 | 4/4 |
| reward-33 | route_10 | 4/4 |
| reward-33 | route_11 | 4/4 |
| reward-33 | route_12 | 4/4 |
| reward-33 | route_13 | 0/4 |
| reward-33 | route_14 | 0/4 |
| reward-33 | route_15 | 0/4 |
| reward-33 | route_16 | 4/4 |

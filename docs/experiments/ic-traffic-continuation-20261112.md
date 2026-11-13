# 트래픽 후속 실험 자동 진행

현재 단계: blocked_av_low

무교통 조합600064 모델(seed11/22/33)을 공통 출발점으로 사용. 강제 보정 없음. 관측47차원.
추가학습은 기존 설계대로 기본 PPO/보상/하이퍼파라미터, optimizer 새 초기화, 단계당800000스텝. 목적지 보상·탐험감소를 트래픽 단계에 동시에 추가하지 않음.
최대6작업 병렬. 매10만 스텝 평가 및 TensorBoard 기록. 최종800000 모델로 다음 단계 기준을 판정; 중간 최고 모델로 몰래 대체하지 않음.

| 실행 | 평가 | 완주 | 충돌 | 통과 |
|---|---|---:|---:|---|
| low-11 | eval-100352.summary | 85/320 | 134 | False |
| low-11 | eval-200704.summary | 98/320 | 119 | False |
| low-11 | eval-301056.summary | 114/320 | 177 | False |
| low-11 | eval-401408.summary | 119/320 | 171 | False |
| low-11 | eval-501760.summary | 125/320 | 115 | False |
| low-11 | eval-600064.summary | 101/320 | 138 | False |
| low-11 | eval-700416.summary | 112/320 | 164 | False |
| low-11 | eval-800000.summary | 104/320 | 202 | False |
| low-11 | evaluation.summary | 104/320 | 202 | False |
| low-11 | initial-eval.summary | 66/320 | 253 | False |
| low-22 | eval-100352.summary | 104/320 | 156 | False |
| low-22 | eval-200704.summary | 101/320 | 111 | False |
| low-22 | eval-301056.summary | 70/320 | 145 | False |
| low-22 | eval-401408.summary | 101/320 | 178 | False |
| low-22 | eval-501760.summary | 117/320 | 93 | False |
| low-22 | eval-600064.summary | 84/320 | 55 | False |
| low-22 | eval-700416.summary | 141/320 | 84 | False |
| low-22 | eval-800000.summary | 87/320 | 130 | False |
| low-22 | evaluation.summary | 87/320 | 130 | False |
| low-22 | initial-eval.summary | 67/320 | 253 | False |
| low-33 | eval-100352.summary | 108/320 | 144 | False |
| low-33 | eval-200704.summary | 43/320 | 149 | False |
| low-33 | eval-301056.summary | 50/320 | 97 | False |
| low-33 | eval-401408.summary | 57/320 | 131 | False |
| low-33 | eval-501760.summary | 65/320 | 195 | False |
| low-33 | eval-600064.summary | 86/320 | 200 | False |
| low-33 | eval-700416.summary | 114/320 | 206 | False |
| low-33 | eval-800000.summary | 142/320 | 132 | False |
| low-33 | evaluation.summary | 142/320 | 132 | False |
| low-33 | initial-eval.summary | 66/320 | 254 | False |
| smoke-11 | eval-2048.summary | 67/320 | 253 | False |
| smoke-11 | evaluation.summary | 67/320 | 253 | False |

기본수요 HV는 기존 재검증에서 미달: 13~15번의 공통 1차로 램프에 2250대/시간이 집중됨. 원래 수요와 통과 기준을 낮추지 않으며, 기본수요 의존 단계는 이 검증 통과 전 실행하지 않음.
ZIP 이벤트는 현 맵에서 미검증이므로 기존 설계대로 제외. 원자료는 로컬 results/traffic_continuation_20261112.

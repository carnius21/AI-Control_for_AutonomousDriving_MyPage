# 경로 안내 구분 및 연속 분기 비교

사용자 승인 순서: ① 계산 불가와 유효 차로 구분 → ② 연속 분기 정보 추가 → ③ 동일 조건 비교 학습.

- [x] 1단계: 현재 목표·준비 목표를 계산할 수 있는지 각각 별도 입력으로 표시. 기존 방향값은 유지.
- [x] 2단계: 300m 내 두 번째 차로 제한 지점의 거리와 해당 지점의 목표 차로 집합을 제공. 서로 다른 도로의 차로 번호를 현재 차로 명령으로 직접 변환하지 않음.
- [x] 단위 검증 5개 통과. 실제 맵에서 03·04의 두 번째 분기 목표가 서로 다르게 전달됨을 확인. 세 조건 각각 2048단계 학습 통과, 행동 강제 보정 0회, 동일 seed 초기 가중치 해시 일치.
- [ ] 기존 안내 / 상태 구분만 추가 / 상태 구분과 다음 분기 추가를 같은 조건으로 새로 학습.

세 조건 모두 입력 47개(기존 37 + 계산 가능 여부 2 + 다음 분기 거리 1·목표 차로 마스크 6·존재 여부 1). 사용하지 않는 입력은 0으로 채워 모델 크기를 통일한다. 신경망 은닉층과 PPO·보상·도로·행동 조건은 유지한다. 경로 ID·주변 차량의 미래 상태·교사 행동은 제공하지 않는다.

학습 seed 11/22/33, 조건별 800000 step, 전체 16경로 무교통, 모든 조건 처음부터 학습한다. 기존 37입력 가중치를 이어 쓰지 않는다. 조건별 초기 가중치 해시를 기록하여 같은 seed에서 일치하는지 검증한다.

평가: 경로마다 기존 best/max 출발과 차로0/속도5, 차로0/속도15, 가장 왼쪽 차로/속도15의 조건을 평가. 삽입 불가는 정책 시간초과와 별도 기록한다. 완주·충돌·시간초과·실패 위치 및 강제 행동 보정0회를 기록한다. 이 제한된 무교통 검증으로 최종 교통 성능이나 95% 신뢰도를 주장하지 않는다.

원본 실험 보존. 새로운 구현은 env/navigation_clarity.py, 실행기는 utils/train_navigation_clarity.py, 원본 산출물은 로컬 results/navigation_clarity_v1/. 각 조건 종료 시 결과 표를 이 문서에 갱신하고 별도 커밋한다. 오류·소스 변경·부분 실행 발견 시 조용히 덮어쓰지 않고 중단한다.

### 실행 속도 개선

학습 예산·학습률·보상·관측·CPU 계산을 유지하고 seed별 독립 프로세스 3개로 병렬화했다. 진행 중이던 seed11의 두 번째 조건은 중단하지 않고 학습·평가·저장을 완료한 뒤 이어받는다. 기존 실행기는 실행기 파일 변경 감지로 다음 조건 시작 전에 종료하며, 이는 의도된 인계다. 완료된 모델 해시·설정·학습 소스가 일치하는지 검증한 뒤 완료 조건을 건너뛴다. 부분 실행은 자동 재학습하지 않는다.

실시간 상태는 `results/navigation_clarity_v1/parallel-status.json`과 `status-11.json`, `status-22.json`, `status-33.json`을 기준으로 본다. 기존 `status.json`에는 인계 시 기존 실행기의 변경 감지 메시지가 남을 수 있다. 각 반복 안의 세 조건은 순차 실행하고, 보고서 갱신과 GitHub 기록은 잠금으로 직렬 처리한다.









## 비교 실행 결과

동일 seed의 세 조건은 같은 초기 가중치에서 시작한다. 삽입 불가는 별도 표기하며 성공으로 처리하지 않는다.

| 조건 | 학습 seed | 완주/전체 | 충돌 | 시간초과 | 삽입 불가 | 실행 경로 |
|---|---:|---:|---:|---:|---:|---|
| baseline | 11 | 62/62 | 0 | 0 | 0 | `results\navigation_clarity_v1\runs\baseline-11` |
| baseline | 22 | 59/62 | 0 | 3 | 0 | `results\navigation_clarity_v1\runs\baseline-22` |
| baseline | 33 | 52/62 | 0 | 10 | 0 | `results\navigation_clarity_v1\runs\baseline-33` |
| lookahead | 11 | 58/62 | 0 | 4 | 0 | `results\navigation_clarity_v1\runs\lookahead-11` |
| lookahead | 22 | 41/62 | 0 | 21 | 0 | `results\navigation_clarity_v1\runs\lookahead-22` |
| lookahead | 33 | 62/62 | 0 | 0 | 0 | `results\navigation_clarity_v1\runs\lookahead-33` |
| validity | 11 | 30/62 | 0 | 32 | 0 | `results\navigation_clarity_v1\runs\validity-11` |
| validity | 22 | 62/62 | 0 | 0 | 0 | `results\navigation_clarity_v1\runs\validity-22` |
| validity | 33 | 44/62 | 0 | 18 | 0 | `results\navigation_clarity_v1\runs\validity-33` |

### 경로별 결과

- baseline-11 / route_01: 3/3 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_02: 3/3 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_03: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_04: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_05: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_06: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_07: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_08: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_09: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_10: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_11: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_12: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_13: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_14: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_15: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-11 / route_16: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- baseline-22 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_02: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_03: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_04: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_05: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_08: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_13: 3/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_14: 3/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_15: 3/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-22 / route_16: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_02: 0/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_03: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_04: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_05: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_08: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_13: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_14: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_15: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- baseline-33 / route_16: 1/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-11 / route_01: 3/3 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_02: 3/3 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_03: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_04: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_05: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_06: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_07: 0/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_08: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_09: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_10: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_11: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_12: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_13: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_14: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_15: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-11 / route_16: 4/4 완주. 실행 코드 `24ccc993f5b7f56adc91d113dc1f734df3b77fd7`.
- lookahead-22 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_02: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_03: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_04: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_05: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_08: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_13: 3/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_14: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_15: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-22 / route_16: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_02: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_03: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_04: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_05: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_08: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_13: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_14: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_15: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- lookahead-33 / route_16: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-11 / route_01: 3/3 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_02: 3/3 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_03: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_04: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_05: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_06: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_07: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_08: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_09: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_10: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_11: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_12: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_13: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_14: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_15: 0/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-11 / route_16: 4/4 완주. 실행 코드 `563cc041256ad05e1334ab232dd627ac016fec81`.
- validity-22 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_02: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_03: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_04: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_05: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_08: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_13: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_14: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_15: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-22 / route_16: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_01: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_02: 3/3 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_03: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_04: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_05: 0/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_06: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_07: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_08: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_09: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_10: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_11: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_12: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_13: 2/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_14: 2/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_15: 2/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.
- validity-33 / route_16: 4/4 완주. 실행 코드 `4f69d3a036e6db1f818931a1ba4ef36e321d48a4`.

## 중간 저장 모델 평가

같은 62개 출발 조건으로 20만·40만·60만 단계 저장 모델을 전수 평가했다. 마지막에 실패한 사례는 이전 성공이 발견될 때까지 나머지 약2만 단계 간격 저장 모델도 확인했다. 이전 성공이 없는 경우 모든 이전 저장 모델에서 실패했음을 뜻하며, 저장 사이의 모든 순간까지 증명하지 않는다.

| 조건 | 초기값 | 20만 | 40만 | 60만 | 80만 | 성공 후 실패 사례 | 저장 모델 전체에서 성공 미관측 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 11 | 42/62 | 62/62 | 50/62 | 62/62 | 0 | 0 |
| baseline | 22 | 62/62 | 47/62 | 62/62 | 59/62 | 3 | 0 |
| baseline | 33 | 62/62 | 59/62 | 62/62 | 52/62 | 10 | 0 |
| lookahead | 11 | 59/62 | 55/62 | 58/62 | 58/62 | 4 | 0 |
| lookahead | 22 | 62/62 | 62/62 | 40/62 | 41/62 | 21 | 0 |
| lookahead | 33 | 59/62 | 58/62 | 58/62 | 62/62 | 0 | 0 |
| validity | 11 | 62/62 | 62/62 | 62/62 | 30/62 | 32 | 0 |
| validity | 22 | 62/62 | 47/62 | 55/62 | 62/62 | 0 | 0 |
| validity | 33 | 59/62 | 62/62 | 59/62 | 44/62 | 18 | 0 |

이는 같은 평가 사례를 돌이켜 본 진단이다. 최고 체크포인트 선택 후 성능은 별도의 미사용 출발 조건에서 검증해야 한다. 원본 기록: `results/navigation_clarity_checkpoints_v1/`. 강제 행동 보정 및 재학습 없음.

### 완료된 진단: 학습 후 성능 저하와 행동 선택 방식

9개 모델의 중간 저장 모델 평가를 3개 작업으로 병렬 완료했다. 최종 실패 88건 모두 동일한 출발 조건에서 이전 저장 모델의 성공이 확인됐다. 기존 관측 13건, 안내 유효성 추가 50건, 연속 분기 안내 추가 25건이다. 따라서 이번 최종 실패를 단순히 처음부터 학습하지 못한 사례로 설명할 수 없다. 다만 과거 한 번의 성공은 안정적인 일반화의 증명이 아니다.

| 관측 조건 (각 3 seed 합계) | 약 20만 단계 | 약 40만 단계 | 약 60만 단계 | 최종 80만 단계 |
|---|---:|---:|---:|---:|
| 기존 관측 | 166/186 (89.25%) | 168/186 (90.32%) | 174/186 (93.55%) | 173/186 (93.01%) |
| 안내 계산 유효성 추가 | 183/186 (98.39%) | 171/186 (91.94%) | 176/186 (94.62%) | 136/186 (73.12%) |
| 유효성 + 연속 분기 안내 | 180/186 (96.77%) | 175/186 (94.09%) | 156/186 (83.87%) | 161/186 (86.56%) |

추가로 대표 실패 3건을 병렬 재현했다. 모델 가중치·도로·관측·출발 조건·가속 명령 계산을 유지하고 차선 행동만 최고 확률 선택에서 정책 확률에 따른 선택으로 변경했다. 강제 차로 보정은 전혀 사용하지 않았다.

| 모델 / 경로 | 최고 확률 행동 선택 | 정지 직전 유지 확률 | 차선 확률 선택 (701/702/703) |
|---|---|---:|---|
| 기존 관측 seed 33 / 08 | 900초 시간 초과 | 52.02% | 3/3 완주, 각 55.0초 |
| 유효성 추가 seed 11 / 04 | 900초 시간 초과 | 80.64% | 3/3 완주, 각 41.2초 |
| 연속 분기 추가 seed 22 / 03 | 900초 시간 초과 | 70.79% | 3/3 완주, 41.8~42.0초 |

가장 높은 확률의 유지 행동을 반복하면 탈출하지 못하지만 다른 차선 행동에도 확률이 남아 있었다. 학습 중 확률적 행동 선택과 실행 시 최고 확률 선택의 차이가 이 세 사례에 영향을 준다는 실험 근거다. 모든 실패의 단일 원인이나, 확률 선택을 도입하면 교통 상황에서도 안전하다는 결론은 아니다. 전체 경로 일반화는 아직 검증하지 않았다. 표의 유지 확률은 마지막 정지 상태의 값이며 최초 실패 시점의 확률과 같다는 뜻도 아니다.

TensorBoard의 9개 학습 로그에서 에피소드 길이 4500스텝(900초)에 도달한 기록은 0건이었다. 학습 중 시간 초과가 기록되지 않아도 결정론적 평가에서는 실패할 수 있음을 보여준다. 길이만으로 모든 학습 에피소드의 정상 도착을 보장하지는 않는다.

별도 코드 검사에서는 시간 초과 후 GAE가 다음 에피소드로 이어지는 오류를 재현했다 (`utils/probe_timeout_bootstrap.py`). 그러나 이번 학습 로그에는 시간 초과가 없으므로 이번 성능 저하의 주원인으로 지목하지 않는다. 이번 진단에서는 학습 코드를 변경하지 않았다.

### 후속 개선 우선순위

1. 마지막 저장 모델을 자동 채택하지 않고, 학습 중 고정된 검증 출발 조건으로 결정론적 완주율을 측정해 최선 모델을 보존한다. 선택에 쓰지 않은 별도 출발 위치·차로·속도로 최종 평가한다. 기존 62개 사례는 이번 분석에 사용했으므로 독립 최종 시험으로 재사용하지 않는다.
2. 기존 관측과 추가 관측 모두에서 학습 후반 차선 탐험 계수 감소를 독립 비교한다. 현재 `lane_entropy_coef=0.01` 유지 조건과 후반 감소 조건을 같은 초기 모델·학습량·seed로 병렬 비교한다. 탐험 계수가 실제 원인인지는 아직 미검증이며, 성공률뿐 아니라 불필요한 차선 변경·경로별 실패·최저 seed 성능을 비교한다.
3. 성능 저하가 남으면 학습률 감소를 별도 비교한다. 관측·보상·학습률·탐험 계수를 한꺼번에 바꾸지 않는다. 보상 추가나 도로 변경보다 학습 안정화와 검증 기준을 먼저 다룬다.
4. 무교통 조건에서 완주율 95% 이상·충돌률 5% 이하를 별도 평가로 확인한 뒤 낮은 교통량으로 확대한다. 확률적 행동은 진단 결과이며 현재 최종 실행 방식으로 채택한 것이 아니다.

실행 기록: `results/navigation_clarity_checkpoints_v1/summary.json`, `sampling-summary.json`, `training-length-audit.json`, `timeout-bootstrap-probe.json`. 정책과 상세 데이터는 로컬에 보존하며 Git에는 코드와 요약만 기록한다. 중간 모델 평가 구현 커밋 `b77df57`, 평가 자료형 수정 및 시간 초과 재현 커밋 `e29950b`. 모델별 원본 학습 커밋과 파일 해시는 각 manifest에 저장되어 있다.

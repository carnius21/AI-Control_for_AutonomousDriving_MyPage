# 14번 순수 PPO 관측 비교 결과

학습·평가는 강제 차로 보정 없이 실행한다. 동일 조건별200,000스텝, seed11/22/33. 각 모델은 출발차로4개×속도5개인20조건으로 검증한다. 이 표는 검증 결과이며 최종100회holdout평가나16경로전체/HV평가가 아니다.

완료: **9/9개 모델**. 미완료 조건은 결과를 추정하지 않는다.

| 관측 | 학습 seed | 완주 | 충돌 | 시간초과 | 삽입 실패 |
|---|---:|---:|---:|---:|---:|
| N0 | 11 | 20/20 | 0 | 0 | 0 |
| N0 | 22 | 20/20 | 0 | 0 | 0 |
| N0 | 33 | 20/20 | 0 | 0 | 0 |
| N1 | 11 | 20/20 | 0 | 0 | 0 |
| N1 | 22 | 20/20 | 0 | 0 | 0 |
| N1 | 33 | 20/20 | 0 | 0 | 0 |
| N2 | 11 | 20/20 | 0 | 0 | 0 |
| N2 | 22 | 20/20 | 0 | 0 | 0 |
| N2 | 33 | 20/20 | 0 | 0 | 0 |

N0=기존 관측, N1=정적 경로 안내, N2=N1+경로별 차로 연결성. 모든완료run에서200,000스텝행동검사·override0·맵스냅샷해시·20평가사례를확인했다. 같은seed의초기모델해시일치도검사했다.

## 반복 평균 (세 seed 모두 완료된 조건만)

| 조건 | 완주율 | 충돌률 |
|---|---:|---:|
| N0 | 100.0% | 0.0% |
| N1 | 100.0% | 0.0% |
| N2 | 100.0% | 0.0% |

## 실행 근거

| 조건/seed | 실행 커밋 | 로컬 결과 | 모델 SHA256 |
|---|---|---|---|
| N0/11 | `dbf958d` | `results\navigation_route14_v1\runs\N0-11-200000` | `b84e12a11b17ef6957d231f7d73ec6195a3190aaee2a01562ab9fce9d465f9b0` |
| N0/22 | `dbf958d` | `results\navigation_route14_v1\runs\N0-22-200000` | `05c897309568756d78c3fa61acf8fe01ccd78b3ae0cde3084ebc243077a000b6` |
| N0/33 | `dbf958d` | `results\navigation_route14_v1\runs\N0-33-200000` | `3ded29bfb0964d14eec17f40153208343dc65d27ea6d32d51f16f5a073c04608` |
| N1/11 | `dbf958d` | `results\navigation_route14_v1\runs\N1-11-200000` | `2d1627b29c063ba117ee24184506a1909c99f5586330f383d2ea1301bbc7626f` |
| N1/22 | `dbf958d` | `results\navigation_route14_v1\runs\N1-22-200000` | `8afbeaeb658f6730fb9d1fb6e8797cdb4ba32a8649fe5b125e1f218d75b266ff` |
| N1/33 | `dbf958d` | `results\navigation_route14_v1\runs\N1-33-200000` | `edb239094575f80b2bc8957453df8a471371847b98850b67f4ab7556eabe92e4` |
| N2/11 | `dbf958d` | `results\navigation_route14_v1\runs\N2-11-200000` | `bdacf6fb2a93d918e4c4d141c6411cac04316ee5d6a54d2819a98d30897a595b` |
| N2/22 | `dbf958d` | `results\navigation_route14_v1\runs\N2-22-200000` | `74248f4310575cb817074bf007e9d81b525781234edead8e2e43757e3dc02560` |
| N2/33 | `dbf958d` | `results\navigation_route14_v1\runs\N2-33-200000` | `fa4f9879a2a01eb789480242e55d3edd06b5d03fb02cea332543b0f0e3dcb301` |

[설계](ic-navigation-learning-plan.md) · [구현·검증](ic-navigation-route14-progress.md)

모델·원시JSON·TensorBoard는로컬results에만저장한다. 이표는완료이벤트마다자동갱신한다.다음경로단계나보상/학습률변경은이자동화에포함하지않는다.

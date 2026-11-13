# 04번 순수 PPO 관측 비교 결과

학습·평가는 강제 차로 보정 없이 실행한다. 동일 조건별200,000스텝, seed11/22/33. 각 모델은 출발차로4개×속도5개인20조건으로 검증한다. 이 표는 검증 결과이며 최종100회holdout평가나16경로전체/HV평가가 아니다.

완료: **9/9개 모델**. 미완료 조건은 결과를 추정하지 않는다.

| 관측 | 학습 seed | 완주 | 충돌 | 시간초과 | 삽입 실패 |
|---|---:|---:|---:|---:|---:|
| N0 | 11 | 20/20 | 0 | 0 | 0 |
| N0 | 22 | 20/20 | 0 | 0 | 0 |
| N0 | 33 | 10/20 | 0 | 10 | 0 |
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
| N0 | 83.3% | 0.0% |
| N1 | 100.0% | 0.0% |
| N2 | 100.0% | 0.0% |

## 실행 근거

| 조건/seed | 실행 커밋 | 로컬 결과 | 모델 SHA256 |
|---|---|---|---|
| N0/11 | `4b9fab9` | `results\navigation_route04_v1\runs\N0-11-200000` | `b6875acb39cabebb45d8381549823d50bd453b0a7c8350bce23a50e25747255e` |
| N0/22 | `4b9fab9` | `results\navigation_route04_v1\runs\N0-22-200000` | `b5205a07b7389f8d5dabe9642e3e1a56fcbacf324859f31d3066be4600aa35b8` |
| N0/33 | `4b9fab9` | `results\navigation_route04_v1\runs\N0-33-200000` | `e3459ab7f55d1fcaf431f8c23ad9d4b1ff011b5dd9446dbf70c09a94e57bdd37` |
| N1/11 | `4b9fab9` | `results\navigation_route04_v1\runs\N1-11-200000` | `d8fd0dab64fdb2e486cfb5133a176b7b8e9a04626e025066491097b34fd8740a` |
| N1/22 | `4b9fab9` | `results\navigation_route04_v1\runs\N1-22-200000` | `809ebb3b71c3b84334553777c6054434cbb7a6db2e6ac2702f9e814c1b361358` |
| N1/33 | `4b9fab9` | `results\navigation_route04_v1\runs\N1-33-200000` | `f29e1b6c5c4e410e90746d00e3231dd72444186d8858b049f30952f5a7016c2b` |
| N2/11 | `4b9fab9` | `results\navigation_route04_v1\runs\N2-11-200000` | `f63491a7cc8237bea76d46b59f1e5221c4e56a221e16af77090d47811461cfb6` |
| N2/22 | `4b9fab9` | `results\navigation_route04_v1\runs\N2-22-200000` | `37d65ee9e5662cf170aa36d83c6c229fbd35a2abbbede8b9e58d7fe6e23dca15` |
| N2/33 | `4b9fab9` | `results\navigation_route04_v1\runs\N2-33-200000` | `98b6d46a001c4a2c28e7a423817cf9e824556ac64bea637b83b8235e8ac17c8e` |

[설계](ic-navigation-learning-plan.md) · [구현·검증](ic-navigation-route04-progress.md)

모델·원시JSON·TensorBoard는로컬results에만저장한다. 이표는완료이벤트마다자동갱신한다.14번이후단계나보상/학습률변경은이자동화에포함하지않는다.

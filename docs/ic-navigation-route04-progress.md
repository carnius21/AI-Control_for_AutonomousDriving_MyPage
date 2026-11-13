# 04번 경로 내비게이션 관측 비교: 구현·학습 착수

상태: 2026-11-07 본 학습 시작. 성능 결과는 아직 확정되지 않았다. [실험 설계](ic-navigation-learning-plan.md)를 따른다.

- 관측 구현: `env/navigation_observation.py`. N0 기존37차원, N1 정적지도 경로안내37차원, N2 경로별 연결성까지37차원. 정책/가감속/차선변경 명령을 목적지 기준으로 덮어쓰지 않는다.
- S0: 차로 번호 재매핑, 복수 목표/왼쪽 출구, 차로 감소, 300m 범위, 도착/내부junction, 짧은 연결의 불가능한 투영을 검증했다. 16경로×3조건×40스텝 동일 입력에서 차로와 속도가 동일했다. 검증 출발차로4개×속도0/5/10/15/20m/s의20조건이 모두 삽입됐다. 삽입 성공은 학습 모델의 완주 성공이 아니다.
- smoke: N0/N1/N2 각각2,048스텝, 모델·CSV·TensorBoard 저장 완료. 세 모델 초기 가중치 텐서가 동일했고 강제 보정0회. smoke의평가사례수0은 미평가라는 뜻이며 완주율0%가 아니다.
- 본 학습: seed11→22→33, 각 seed마다 N0→N1→N2, 200,000스텝씩 새 초기화. 총9회·1.8M스텝. epoch/lr/gamma/보상/행동제약/맵 모두 고정.
- 완료 후 검증: 각 모델에 고정된20개 출발조건, simulation seed20001~20020. 최종holdout30001~30100은 사용하지 않는다.20회결과로 최종95%달성을 주장하지 않는다.

## 저장·재현

실행 커밋 `4b9fab9`, 구현 커밋 `c95a421`. 시작 시 코드·설정·맵 스냅샷을 각run에 저장한다. 학습용 에피소드 seed는 환경 RNG로 생성하고 action-audit에 실제 목록을 기록한다. 기존 helper의고정1001메타데이터는 이학습에맞지 않아 수정했으며 smoke자료의잘못된상수라벨도정정했다.

- 검증 실행: `python -m utils.validate_navigation_observation`
- 시험 학습: `python -m utils.train_navigation_route04 smoke`
- 본 학습: `python -m utils.train_navigation_route04 train`
- 로컬 결과: `results/navigation_route04_v1/`
- 실시간 진행: `status.json`, `runs/<조건>-<seed>-200000/progress.json`
- 모델/로그: 같은run의 `model.pt`, `policy-*.pt`, `tb/`, `training_log.csv`
- 완료 결과: `evaluation.json`, `complete.json`
- 명령 검증: `action-audit.json`의 checked_steps, route_override_count, episode_seeds

실행중중복방지를위해active.lock을사용한다. 완료된run은건너뛰지만미완료run은자동이어학습하지않고오류로멈춰기록을보존한다. 학습모델/원자료는gitignore로로컬보관하며GitHub에는요약만추가한다.

20k단위체크포인트는rollout경계에서저장하므로20,480등실제스텝을파일명에남긴다. 마지막은exact_budget으로정확히200,000스텝이다. 손실과모델수치는유한값을검사하고, 아직종료episode가없는구간의ep_rew_mean=NaN은손실오류와구분한다.

## 범위와 남은 확인

정적내비게이션은첫준비지점까지차로연결을역추적한다. 투영가능차로가없으면ambiguous로표시하며정답차로를꾸며내지않는다. 서로충돌하는여러분기전체를풀어주는경로계획기는아니다. 기존실선·입구보호·안전검사를완화하지않았다. 현재실험은04번무교통뿐이며14번·전체16경로·HV평가를자동실행하지않는다.

- [x] 관측 구현 및 정적·동일행동 검증
- [x] 세 조건 시험학습과 초기화 일치 확인
- [x] 04번 본 학습 실행
- [ ] 9개 모델 학습·검증 완료 및 조건별 비교
- [ ] 필요 원인 분석 후14번 단계 결정

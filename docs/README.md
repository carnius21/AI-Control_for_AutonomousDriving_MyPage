# 팀 프로젝트 문서

현재 상태(2026-11-13): **AV 실험을 중단하고 HV 수요·병목을 먼저 검증 중**입니다. 아래 과거 AV 결과와 현재 HV 검증을 구분해 참고하세요. 규칙 보정48/48은 PPO 학습 성능이 아닙니다.

| 문서 | 용도 |
|---|---|
| [실측 교통량 재조사·HV 시험](experiments/ic-observed-bounds-20261113.md) | 본선 관측값, 미확인 램프·일반도로 분배 가정, 고정 수요 시험 |
| [후속 자동 실험](ic-next-stages-plan.md) | HV → 기존 AV 트래픽 → 공유 정책 → 트래픽 학습, 통과 기준 적용 |
| [14번 완료 결과](ic-navigation-route14-results.md) | N0/N1/N2 모두 60/60 완주 |
| [14번 검증·학습 진행](ic-navigation-route14-progress.md) | 사전 검증 완료, 동일 조건 비교 |
| [04번 완료 결과](ic-navigation-route04-results.md) | N0 50/60, N1·N2 각 60/60 완주 |
| [현재 실험 설계](ic-navigation-learning-plan.md) | 강제 보정 제외, 수업 기준에 맞춘 관측 비교·재학습 계획 |
| [최신 원인 분석](ic-toegyewon-lane-cause-results.md) | 기본 PPO32/48, 실패 원인과 진단 개입의 구분 |
| [맵 수정 기록](ic-map-geometry-review.md) | 수정·정정 순서와 현재 분기 구조 검증 |
| [수업 평가 기준](../project_materials/6_Project_Evaluation.md) | 원본 수업 요구사항 |
| [데이터 보관 정책](../data/README.md) | GitHub와 로컬에 보관할 파일 구분 |
| [과거 문서 보관함](archive/README.md) | 이전 설계·실패 실험·맵 기록 |

원본 수업 자료는 project_materials에 유지합니다. 소형 실험 설정과 설계 JSON은 Git에서 관리하고, 개별 사례·추적·학습 데이터는 로컬에 보존합니다.

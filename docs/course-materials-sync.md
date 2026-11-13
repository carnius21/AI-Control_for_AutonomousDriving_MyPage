# 수업 자료 동기화 기록

- 확인일: 2026-11-03
- 수업 원본: https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving
- 원본 main SHA: `2e01bbacebb978a9d3122b7cc3d05b1f80dcbf65`
- 팀 main 기준: `be62cc7`

## 반영 범위

누락된 project_materials/5_Project_Preparation.md, 6_Project_Evaluation.md, 7_Project_Consulting.md를 원본 그대로 추가했다. 기존 0~4번 자료는 Git 비교상 같았다. project_materials/UPSTREAM_README.md는 최신 원본 README를 그대로 보관하며 팀 README는 팀 링크와 내용을 유지했다. 새 파일과 링크는 원본 SHA 기준으로 검증한다.

팀 체크리스트·데이터 안내·실험 설계를 최신 평가 요구에 맞췄다. 원본 문서의 표기 불일치는 원문을 고치지 않고 팀 문서에 설명했다. 충돌률은 전용 평가 문서의 <5%를 따른다. 데이터 개수 단위, 추가 칼럼 범위, 정확한 최종 제출 마감은 확인 대기다.

## 코드 및 생성물 차이

학습·수집 Python 파일을 줄바꿈 차이를 제외해 비교하면 train.py의 학습률이 원본 1e-4 / 팀 3e-4로 다르다. train_bc.py와 collect_pomdp_data.py는 줄바꿈 제외 내용이 동일하다. 이번 동기화는 수업 자료와 팀 문서에 한정하여 학습률을 변경하지 않았다. 생성된 SUMO XML, 예시 학습 결과/model.pt, 팀 전용 requirements·웹페이지는 원본 파일로 덮어쓰지 않았다.

영훈님 kyh 최종 맵은 업로드 대기이며 이번 작업에 병합하지 않았다. jys의 기존 구현·결과도 main에 병합하지 않았다.

## 기존 자동 기록 확인

- train.py의 snapshot_configs: train.py, env/road_config.py, env/mdp_config.py를 결과 run 폴더로 복사.
- 실행 위치: finally의 모델 저장 이후. 실행 시작 스냅샷이 아니므로 실행 중 파일 수정 금지.
- utils/logger.py: training_log.csv, eval_log.csv, 선택적 tb/ 기록.
- train_bc.py: 실행 설정 config.json 저장.
- collect_pomdp_data.py: NPZ/JSONL 주행 데이터 저장. PPO 설정 스냅샷 자동 첨부와는 별도.

설정 스냅샷은 별도 실험 브랜치/JSON 체계의 필수성을 없애지만, 변경된 환경 로직·맵·데이터 출처까지 자동 보존하지는 않는다. 이 부분만 실험 메타데이터로 보완할 계획이다. 학습 코드 자체는 이번에 변경하지 않았다.

# 퇴계원IC — V / jys 도로 환경

현재 기본 실행은 **ego 없는 배경 교통 안정화 버전**입니다. 두 금강로 합류부를 협조 합류로 변경하고, 30분 수요 뒤 최대 10분 동안 차량이 빠져나가도록 합니다. [설정·검증·한계](TRAFFIC.md)를 먼저 확인하세요.

## 실행

Windows: 이 폴더의 **open_sumo.cmd**를 더블클릭한 뒤 재생합니다.

```powershell
python scenarios/toegyewon/traffic.py --gui
# 설정 변경 후 재생성 및 전체 검증
python scenarios/toegyewon/traffic.py --validate
```

- 기본 설정: traffic_config.json, 생성된 실행 파일: traffic/traffic.sumocfg
- ego 0대, 배경 승용차 Krauss/IDM/EIDM/ACC와 IDM 버스
- 위반 차량·긴급 회피 감독기는 이번 안정화 기준에서 제외
- 차량 화면 배율 1, 기존 실선·점선 그림과 차선 변경 제한 유지
- 차량 순간이동 해제, 충돌 검사 유지

![기존 OSM 도로 구성도](preview.png)

## 도로와 근거

사용자가 지정한 퇴계원IC의 하단 루프, 상단 루프, 동측 엇갈림 구간과 바깥 진출입부입니다. 약 동서 0.88km × 남북 1.22km 범위이며 기존 수업 고속도로 파일은 변경하지 않습니다.

- source.osm.xml: 2026-10-29 OSM 중심선·연결·일방통행 스냅샷
- parameters.json: 교통 수요와 원본 생성 기본값. 안정화 실행 시간은 traffic_config.json을 사용합니다.
- rules_v2/: 부분 판독한 차선 표시 및 변경 제한. [근거와 미확인 구간](RULES_V2.md)
- 교량은 서로 다른 노드·연결로 유지합니다. 화면에서 겹쳐도 갈아탈 수 없습니다. 실제 고도·경사는 모델링하지 않습니다.
- 차선 수, 속도, 합류 위치와 우선권은 실측 교통 보정이 끝나지 않았습니다. 현재 지퍼 합류는 시뮬레이션 안정화를 위한 가정이며 실제 우선권 확정이 아닙니다.

## 이전 버전

toegyewon.sumocfg, build.py, run.py, run_rules.py는 구형 ego 포함 환경의 재현용입니다. 현재 기본 실행은 open_sumo.cmd 또는 traffic.py를 사용하세요. build.py/build_markings.py를 수정·실행했다면 traffic.py로 안정화 버전도 다시 생성해야 합니다.

이전에 수집한 퇴계원IC 데이터와 비교 결과는 폐기했습니다. [폐기 범위와 사유](CONTROLLER_COMPARISON.md). 예전 validation.json은 짧은 원본 환경의 역사적 결과이며 현재 도로 검증은 traffic/validation.json입니다.

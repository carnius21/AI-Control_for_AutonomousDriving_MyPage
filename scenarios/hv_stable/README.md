# HV 전용 검증 시나리오

AV 없이 퇴계원IC의 16개 경로에 HV를 투입하는 교통 기준 조건이다.
원본 `maps/toegyewon_only/network.net.xml`과 기존 실험은 보존했다.
이 폴더의 network, routes, config는 1시간 검증에 사용한 입력과 SHA256이 동일하다.

## 실행

SUMO-GUI에서 이 폴더의 **run.sumocfg**를 열고 실행한다.
명령줄에서는 저장소 루트에서 다음과 같이 실행한다.

```powershell
& "$env:SUMO_HOME/bin/sumo-gui.exe" -c scenarios/hv_stable/run.sumocfg --seed 4001
```

차량은 0~3600초 동안 유입된다. 모든 차량이 나갈 때까지 실행한다.
검증된 seed 4001~4006에서는 마지막 차량이 3688.6~3699.2초에 도착했다.
AV 학습은 재개하지 않았으며, 기존 AV 실행기는 이 설정으로 자동 변경되지 않는다.

## 수정 사항

| 항목 | 적용 |
|---|---|
| 도로 형상 | 모든 외부·내부 차로 형상, 길이, 폭, 연결, 통행·차로 변경 권한 보존 |
| 합류 | 단순 합류 3곳의 우선권/충돌 관계만 netconvert의 zipper 표로 변경 |
| 엇갈림 접근 속도 | 170059991, 170059995, 170059994의 운용 속도 22.22→11.11m/s(40km/h) |
| 북쪽 분배 | 13·14·15번 각 750→200, 16번 750→2400대/시간 |
| 남쪽 분배 | 03·04·05번 각 600→450, 06번 600→1050대/시간 |
| 총수요 | 10,200대/시간 유지 |
| 차량 | 4종 추종 모델 혼합, 버스 5%, 승용차 중 비협조 운전자 2% |
| 비협조 행동 | 해당 vType만 lcCooperative=0, lcCooperativeSpeed=0. 기본 안전 검사는 유지 |
| 안전 확인 | 교차로 내부 충돌 검출 활성화, 텔레포트 비활성화 |

수요 비율과 40km/h는 **시뮬레이션의 안정적인 운영 조건**이며 실측 교통량·법정 제한속도라고 주장하지 않는다.
총량은 같지만 경로별 수요는 달라졌다. 기존 모델과 비교할 때 두 모델 모두 이 동일한 교통 입력을 사용해야 한다.
버스 및 비협조 차량은 확률적으로 배정되므로 개별 실행의 실제 비율은 정확히 5%/2%로 고정되지 않는다.
비협조 설정은 차로 변경 양보를 줄이는 것이며 모든 종류의 불법 운전을 구현한 것은 아니다.

## 검증

- 최종 조건 15분 유입: seed 1001~1003, 각 2552대 전부 도착.
- 최종 조건 1시간 유입: seed 4001~4006, 각 10200대 전부 도착.
- 저수요(20%) 10분: seed 5001~5003, 전부 도착.
- 위 12회 모두 충돌·텔레포트·최종 잔류·미삽입 0.
- 이는 검증한 수요/seed 범위의 결과다. 수요나 맵을 변경하면 다시 검증한다.
- 급제동 경고는 일부 남아 있으므로 승차감까지 최적화됐다는 뜻은 아니다.

[진단 및 단계별 결과](../../docs/experiments/ic-hv-flow-audit-20261113.md)

## 재현/재생성

```powershell
python -m utils.hv_flow_repair --modes drivers --seeds 4001 4002 4003 4004 4005 4006 --duration 3600 --horizon 7200 --output results/hv_flow_repair_20261113/drivers-long
python -m unittest discover -s tests -v
python -m utils.hv_flow_repair --modes drivers --duration 3600 --horizon 7200 --output results/hv_flow_repair_20261113/export --export scenarios/hv_stable
```

재생성에 필요한 원래 수요는 `source.rou.xml`, 원본 맵은 `maps/toegyewon_only/network.net.xml`이다.
로컬 results 파일 없이도 재생성할 수 있다. 다른 설정 시험은 새 output 폴더를 사용한다.
큰 로그와 차량별 결과는 results 아래 로컬에 저장하고 Git에는 실행 입력과 요약만 둔다.

참고: [SUMO 차량/차로 변경 설정](https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html)

## 높은 트래픽

전체15,000대/h의 높은 트래픽은 별도 [hv_high15000](../hv_high15000/README.md) 프로필을 사용한다. 기본10,200대/h 파일은 변경하지 않는다.

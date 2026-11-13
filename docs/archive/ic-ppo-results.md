> **과거 기록** — 작성 당시의 설계·맵·결과입니다. 현재 적용 기준은 [최신 문서 목록](../README.md)을 확인하세요.

# 퇴계원IC PPO 실험 결과

평가를 마친 조건만 표시한다. 1만 스텝은 기능 점검이며, 본 실험은 조건별 20만 스텝이다.

|조건|seed|학습 스텝|평가 에피소드|완주|충돌|시간 초과|기준 대비 완주/충돌|학습 시간(분)|
|---|---:|---:|---:|---:|---:|---:|---|---:|
|BLOCK-11-10000|11|10,000|22|13.6%|72.7%|13.6%|+0.0%p / +50.0%p|0.7|
|BLOCK-11-200000|11|200,000|110|30.9%|28.2%|40.9%|-19.1%p / -3.6%p|12.1|
|COMBO-11-200000|11|200,000|110|51.8%|24.5%|23.6%|+1.8%p / -7.3%p|13.3|
|COMBO-22-200000|22|200,000|110|15.5%|53.6%|30.9%|-28.2%p / +0.0%p|15.0|
|COMBO-33-200000|33|200,000|110|33.6%|30.0%|36.4%|-10.9%p / -11.8%p|16.4|
|COMBO025-11-200000|11|200,000|110|36.4%|28.2%|35.5%|-13.6%p / -3.6%p|19.8|
|COMBO025-22-200000|22|200,000|110|33.6%|16.4%|50.0%|-10.0%p / -37.3%p|16.2|
|COMBO025-33-200000|33|200,000|110|27.3%|20.0%|52.7%|-17.3%p / -21.8%p|13.4|
|COMBO025-NO-RAMP-11-200000|11|200,000|110|35.5%|9.1%|55.5%|-14.5%p / -22.7%p|16.9|
|COMBO025-NO-ROUTE100-11-200000|11|200,000|110|40.9%|12.7%|46.4%|-9.1%p / -19.1%p|16.8|
|COMBO025-NO-ZIP-11-200000|11|200,000|110|33.6%|19.1%|47.3%|-16.4%p / -12.7%p|19.1|
|GAP-11-10000|11|10,000|22|0.0%|18.2%|81.8%|-13.6%p / -4.5%p|0.7|
|GAP-11-200000|11|200,000|110|37.3%|40.0%|22.7%|-12.7%p / +8.2%p|11.3|
|H-LR-11-200000|11|200,000|110|18.2%|10.0%|71.8%|-31.8%p / -21.8%p|16.9|
|H-LR-22-200000|22|200,000|110|25.5%|15.5%|59.1%|-18.2%p / -38.2%p|12.6|
|PREP-11-10000|11|10,000|22|9.1%|81.8%|9.1%|-4.5%p / +59.1%p|1.0|
|PREP-11-200000|11|200,000|110|32.7%|14.5%|52.7%|-17.3%p / -17.3%p|12.1|
|R0-11-10000|11|10,000|22|13.6%|22.7%|63.6%|+0.0%p / +0.0%p|0.9|
|R0-11-200000|11|200,000|110|50.0%|31.8%|18.2%|+0.0%p / +0.0%p|11.9|
|R0-22-200000|22|200,000|110|43.6%|53.6%|2.7%|+0.0%p / +0.0%p|20.1|
|R0-33-200000|33|200,000|110|44.5%|41.8%|13.6%|+0.0%p / +0.0%p|19.2|
|RAMP-11-10000|11|10,000|22|18.2%|45.5%|36.4%|+4.5%p / +22.7%p|0.9|
|RAMP-11-200000|11|200,000|110|22.7%|39.1%|38.2%|-27.3%p / +7.3%p|12.6|
|ROUTE100-11-200000|11|200,000|110|31.8%|28.2%|40.0%|-18.2%p / -3.6%p|17.4|
|ZIP-11-10000|11|10,000|22|13.6%|22.7%|63.6%|+0.0%p / +0.0%p|0.7|
|ZIP-11-200000|11|200,000|110|31.8%|12.7%|55.5%|-18.2%p / -19.1%p|12.6|

지퍼 준수와 준비 성공률은 해당 사건만 분모로 사용한다. 해당 사건이 없으면 ‘관측 없음’으로 표시한다.

|조건|100m 준비|지퍼 준수|램프 과속 시간 비율|최대 초과(km/h)|완주 평균(초)|
|---|---:|---:|---:|---:|---:|
|BLOCK-11-10000|7/7 (100.0%)|관측 없음|63/84 (75.0%)|14.3|35.4|
|BLOCK-11-200000|35/39 (89.7%)|2/6 (33.3%)|1093/9678 (11.3%)|53.5|73.1|
|COMBO-11-200000|40/40 (100.0%)|0/4 (0.0%)|1758/19491 (9.0%)|60.0|75.2|
|COMBO-22-200000|35/35 (100.0%)|0/4 (0.0%)|511/2521 (20.3%)|60.0|66.3|
|COMBO-33-200000|44/48 (91.7%)|4/4 (100.0%)|827/15667 (5.3%)|50.0|74.0|
|COMBO025-11-200000|40/40 (100.0%)|1/3 (33.3%)|412/2854 (14.4%)|60.0|65.2|
|COMBO025-22-200000|40/40 (100.0%)|0/1 (0.0%)|631/22562 (2.8%)|50.0|109.4|
|COMBO025-33-200000|37/40 (92.5%)|3/5 (60.0%)|709/1779 (39.9%)|59.6|106.7|
|COMBO025-NO-RAMP-11-200000|40/50 (80.0%)|3/4 (75.0%)|1612/16179 (10.0%)|60.0|69.5|
|COMBO025-NO-ROUTE100-11-200000|44/55 (80.0%)|0/5 (0.0%)|919/25788 (3.6%)|60.0|89.5|
|COMBO025-NO-ZIP-11-200000|39/51 (76.5%)|2/3 (66.7%)|651/24073 (2.7%)|60.0|83.4|
|GAP-11-10000|6/6 (100.0%)|관측 없음|0/13413 (0.0%)|0.0|완주 없음|
|GAP-11-200000|40/40 (100.0%)|0/2 (0.0%)|1081/8124 (13.3%)|42.3|87.3|
|H-LR-11-200000|40/40 (100.0%)|0/2 (0.0%)|713/22512 (3.2%)|50.0|92.8|
|H-LR-22-200000|37/40 (92.5%)|3/4 (75.0%)|837/2076 (40.3%)|26.5|91.0|
|PREP-11-10000|7/7 (100.0%)|관측 없음|3/3 (100.0%)|20.8|31.4|
|PREP-11-200000|40/40 (100.0%)|0/3 (0.0%)|599/9545 (6.3%)|47.5|79.9|
|R0-11-10000|6/6 (100.0%)|관측 없음|0/21655 (0.0%)|0.0|92.5|
|R0-11-200000|40/40 (100.0%)|0/4 (0.0%)|1270/7395 (17.2%)|60.0|114.0|
|R0-22-200000|19/45 (42.2%)|0/5 (0.0%)|619/5974 (10.4%)|60.0|73.9|
|R0-33-200000|40/40 (100.0%)|0/4 (0.0%)|1111/11635 (9.5%)|58.8|67.6|
|RAMP-11-10000|9/11 (81.8%)|0/1 (0.0%)|57/1118 (5.1%)|56.8|51.0|
|RAMP-11-200000|39/39 (100.0%)|0/4 (0.0%)|305/2320 (13.1%)|60.0|59.6|
|ROUTE100-11-200000|35/44 (79.5%)|2/4 (50.0%)|980/1987 (49.3%)|50.7|65.9|
|ZIP-11-10000|6/6 (100.0%)|관측 없음|0/21655 (0.0%)|0.0|92.5|
|ZIP-11-200000|40/40 (100.0%)|1/2 (50.0%)|618/23627 (2.6%)|45.0|69.5|

<details><summary>BLOCK-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|0.0%|100.0%|0.0%|
|east_to_north|1|0.0%|100.0%|0.0%|
|east_to_south|1|0.0%|100.0%|0.0%|
|north_through|1|100.0%|0.0%|0.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|100.0%|0.0%|
|sano_north_through|1|0.0%|100.0%|0.0%|
|sano_north_to_west|1|0.0%|100.0%|0.0%|
|sano_south_through|1|100.0%|0.0%|0.0%|
|sano_south_to_east|1|0.0%|100.0%|0.0%|
|sano_south_to_west|1|0.0%|0.0%|100.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|100.0%|0.0%|0.0%|
|south_to_east|1|0.0%|100.0%|0.0%|
|south_to_local|1|0.0%|100.0%|0.0%|
|south_to_west|1|0.0%|100.0%|0.0%|
|west_through|1|0.0%|100.0%|0.0%|
|west_to_local|1|0.0%|100.0%|0.0%|

</details>

<details><summary>BLOCK-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|60.0%|40.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|20.0%|40.0%|40.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|20.0%|40.0%|40.0%|
|north_to_west|5|0.0%|0.0%|100.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|100.0%|0.0%|
|sano_north_through|5|0.0%|100.0%|0.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|20.0%|0.0%|80.0%|
|sano_west_to_north|5|0.0%|60.0%|40.0%|
|sano_west_to_south|5|0.0%|60.0%|40.0%|
|south_through|5|80.0%|20.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|20.0%|80.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|80.0%|20.0%|0.0%|
|west_to_local|5|0.0%|100.0%|0.0%|

</details>

<details><summary>COMBO-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|60.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|40.0%|60.0%|0.0%|
|north_to_local|5|40.0%|20.0%|40.0%|
|north_to_west|5|20.0%|80.0%|0.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|80.0%|20.0%|0.0%|
|sano_north_through|5|60.0%|20.0%|20.0%|
|sano_north_to_west|5|60.0%|40.0%|0.0%|
|sano_south_through|5|80.0%|20.0%|0.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|40.0%|60.0%|0.0%|
|sano_west_to_north|5|0.0%|20.0%|80.0%|
|sano_west_to_south|5|0.0%|20.0%|80.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|60.0%|40.0%|0.0%|
|west_through|5|20.0%|80.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>COMBO-22-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|80.0%|20.0%|
|east_to_north|5|60.0%|40.0%|0.0%|
|east_to_south|5|80.0%|20.0%|0.0%|
|north_through|5|40.0%|40.0%|20.0%|
|north_to_east|5|0.0%|20.0%|80.0%|
|north_to_local|5|0.0%|20.0%|80.0%|
|north_to_west|5|0.0%|60.0%|40.0%|
|outer_to_south|5|40.0%|60.0%|0.0%|
|sano_east_to_south|5|0.0%|100.0%|0.0%|
|sano_north_through|5|0.0%|100.0%|0.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|0.0%|80.0%|20.0%|
|sano_south_to_east|5|0.0%|100.0%|0.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|60.0%|40.0%|
|south_to_local|5|0.0%|60.0%|40.0%|
|south_to_west|5|0.0%|60.0%|40.0%|
|west_through|5|20.0%|80.0%|0.0%|
|west_to_local|5|0.0%|100.0%|0.0%|

</details>

<details><summary>COMBO-33-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|100.0%|0.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|80.0%|20.0%|0.0%|
|north_through|5|40.0%|60.0%|0.0%|
|north_to_east|5|0.0%|20.0%|80.0%|
|north_to_local|5|20.0%|20.0%|60.0%|
|north_to_west|5|0.0%|20.0%|80.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|20.0%|80.0%|
|sano_north_through|5|0.0%|100.0%|0.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|20.0%|80.0%|0.0%|
|sano_west_to_south|5|20.0%|80.0%|0.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|40.0%|60.0%|
|south_to_local|5|0.0%|40.0%|60.0%|
|south_to_west|5|0.0%|40.0%|60.0%|
|west_through|5|40.0%|60.0%|0.0%|
|west_to_local|5|20.0%|40.0%|40.0%|

</details>

<details><summary>COMBO025-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|100.0%|0.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|40.0%|60.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|0.0%|40.0%|60.0%|
|north_to_local|5|0.0%|40.0%|60.0%|
|north_to_west|5|0.0%|100.0%|0.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|20.0%|80.0%|
|sano_north_through|5|0.0%|20.0%|80.0%|
|sano_north_to_west|5|20.0%|0.0%|80.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|40.0%|60.0%|0.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|60.0%|40.0%|
|south_to_local|5|0.0%|60.0%|40.0%|
|south_to_west|5|0.0%|60.0%|40.0%|
|west_through|5|100.0%|0.0%|0.0%|
|west_to_local|5|0.0%|20.0%|80.0%|

</details>

<details><summary>COMBO025-22-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|60.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|40.0%|20.0%|40.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|80.0%|20.0%|0.0%|
|north_to_west|5|0.0%|0.0%|100.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|100.0%|0.0%|0.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|80.0%|20.0%|
|sano_south_through|5|20.0%|60.0%|20.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|0.0%|20.0%|80.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|0.0%|20.0%|80.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>COMBO025-33-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|60.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|40.0%|40.0%|20.0%|
|north_to_east|5|0.0%|40.0%|60.0%|
|north_to_local|5|0.0%|20.0%|80.0%|
|north_to_west|5|0.0%|40.0%|60.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|0.0%|100.0%|
|sano_north_through|5|0.0%|20.0%|80.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|0.0%|60.0%|40.0%|
|sano_west_to_south|5|0.0%|60.0%|40.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|20.0%|80.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>COMBO025-NO-RAMP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|100.0%|0.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|80.0%|20.0%|0.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|20.0%|0.0%|80.0%|
|north_to_west|5|0.0%|0.0%|100.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|0.0%|100.0%|
|sano_north_through|5|0.0%|40.0%|60.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|0.0%|0.0%|100.0%|
|sano_west_to_south|5|0.0%|0.0%|100.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|40.0%|60.0%|
|south_to_local|5|0.0%|40.0%|60.0%|
|south_to_west|5|0.0%|40.0%|60.0%|
|west_through|5|80.0%|20.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>COMBO025-NO-ROUTE100-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|40.0%|20.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|60.0%|20.0%|20.0%|
|north_to_west|5|0.0%|0.0%|100.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|0.0%|100.0%|
|sano_north_through|5|20.0%|80.0%|0.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|80.0%|20.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|20.0%|80.0%|
|sano_west_to_north|5|20.0%|0.0%|80.0%|
|sano_west_to_south|5|60.0%|40.0%|0.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|20.0%|80.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|40.0%|20.0%|40.0%|
|west_to_local|5|80.0%|20.0%|0.0%|

</details>

<details><summary>COMBO025-NO-ZIP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|60.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|0.0%|0.0%|100.0%|
|north_to_west|5|0.0%|20.0%|80.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|60.0%|40.0%|
|sano_north_through|5|0.0%|100.0%|0.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|20.0%|20.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|40.0%|60.0%|0.0%|
|west_to_local|5|40.0%|60.0%|0.0%|

</details>

<details><summary>GAP-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|0.0%|0.0%|100.0%|
|east_to_north|1|0.0%|0.0%|100.0%|
|east_to_south|1|0.0%|0.0%|100.0%|
|north_through|1|0.0%|0.0%|100.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|0.0%|100.0%|
|sano_north_through|1|0.0%|0.0%|100.0%|
|sano_north_to_west|1|0.0%|0.0%|100.0%|
|sano_south_through|1|0.0%|0.0%|100.0%|
|sano_south_to_east|1|0.0%|0.0%|100.0%|
|sano_south_to_west|1|0.0%|0.0%|100.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|0.0%|0.0%|100.0%|
|south_to_east|1|0.0%|0.0%|100.0%|
|south_to_local|1|0.0%|0.0%|100.0%|
|south_to_west|1|0.0%|0.0%|100.0%|
|west_through|1|0.0%|0.0%|100.0%|
|west_to_local|1|0.0%|0.0%|100.0%|

</details>

<details><summary>GAP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|100.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|0.0%|100.0%|0.0%|
|north_to_east|5|0.0%|80.0%|20.0%|
|north_to_local|5|100.0%|0.0%|0.0%|
|north_to_west|5|0.0%|80.0%|20.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|100.0%|0.0%|0.0%|
|sano_north_through|5|80.0%|20.0%|0.0%|
|sano_north_to_west|5|0.0%|80.0%|20.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|0.0%|20.0%|80.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|20.0%|80.0%|0.0%|
|south_to_east|5|0.0%|60.0%|40.0%|
|south_to_local|5|20.0%|40.0%|40.0%|
|south_to_west|5|0.0%|40.0%|60.0%|
|west_through|5|0.0%|100.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>H-LR-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|60.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|0.0%|40.0%|60.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|100.0%|0.0%|0.0%|
|north_to_west|5|0.0%|0.0%|100.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|0.0%|100.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|0.0%|0.0%|100.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|0.0%|40.0%|60.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|0.0%|0.0%|100.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>H-LR-22-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|20.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|40.0%|40.0%|20.0%|
|north_to_east|5|0.0%|20.0%|80.0%|
|north_to_local|5|0.0%|20.0%|80.0%|
|north_to_west|5|0.0%|20.0%|80.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|20.0%|80.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|80.0%|0.0%|20.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|20.0%|80.0%|
|sano_west_to_north|5|0.0%|60.0%|40.0%|
|sano_west_to_south|5|0.0%|60.0%|40.0%|
|south_through|5|80.0%|20.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|20.0%|0.0%|80.0%|
|west_to_local|5|0.0%|20.0%|80.0%|

</details>

<details><summary>PREP-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|0.0%|100.0%|0.0%|
|east_to_north|1|0.0%|100.0%|0.0%|
|east_to_south|1|0.0%|100.0%|0.0%|
|north_through|1|100.0%|0.0%|0.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|100.0%|0.0%|
|sano_north_through|1|0.0%|100.0%|0.0%|
|sano_north_to_west|1|0.0%|100.0%|0.0%|
|sano_south_through|1|0.0%|100.0%|0.0%|
|sano_south_to_east|1|0.0%|100.0%|0.0%|
|sano_south_to_west|1|0.0%|100.0%|0.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|100.0%|0.0%|0.0%|
|south_to_east|1|0.0%|100.0%|0.0%|
|south_to_local|1|0.0%|100.0%|0.0%|
|south_to_west|1|0.0%|100.0%|0.0%|
|west_through|1|0.0%|100.0%|0.0%|
|west_to_local|1|0.0%|100.0%|0.0%|

</details>

<details><summary>PREP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|60.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|60.0%|20.0%|20.0%|
|north_to_east|5|0.0%|60.0%|40.0%|
|north_to_local|5|60.0%|40.0%|0.0%|
|north_to_west|5|0.0%|40.0%|60.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|100.0%|0.0%|0.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|0.0%|0.0%|100.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|0.0%|0.0%|100.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|0.0%|20.0%|80.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>R0-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|100.0%|0.0%|0.0%|
|east_to_north|1|0.0%|0.0%|100.0%|
|east_to_south|1|0.0%|0.0%|100.0%|
|north_through|1|0.0%|100.0%|0.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|0.0%|100.0%|
|sano_north_through|1|100.0%|0.0%|0.0%|
|sano_north_to_west|1|0.0%|0.0%|100.0%|
|sano_south_through|1|0.0%|0.0%|100.0%|
|sano_south_to_east|1|0.0%|0.0%|100.0%|
|sano_south_to_west|1|0.0%|0.0%|100.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|0.0%|0.0%|100.0%|
|south_to_east|1|0.0%|0.0%|100.0%|
|south_to_local|1|0.0%|0.0%|100.0%|
|south_to_west|1|0.0%|0.0%|100.0%|
|west_through|1|100.0%|0.0%|0.0%|
|west_to_local|1|0.0%|0.0%|100.0%|

</details>

<details><summary>R0-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|60.0%|0.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|60.0%|40.0%|0.0%|
|north_to_east|5|80.0%|20.0%|0.0%|
|north_to_local|5|80.0%|20.0%|0.0%|
|north_to_west|5|40.0%|20.0%|40.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|80.0%|20.0%|0.0%|
|sano_north_through|5|40.0%|60.0%|0.0%|
|sano_north_to_west|5|40.0%|60.0%|0.0%|
|sano_south_through|5|80.0%|20.0%|0.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|60.0%|40.0%|0.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|0.0%|40.0%|60.0%|
|south_to_east|5|0.0%|60.0%|40.0%|
|south_to_local|5|0.0%|60.0%|40.0%|
|south_to_west|5|40.0%|60.0%|0.0%|
|west_through|5|60.0%|40.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>R0-22-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|100.0%|0.0%|0.0%|
|east_to_north|5|20.0%|80.0%|0.0%|
|east_to_south|5|20.0%|80.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|20.0%|80.0%|0.0%|
|north_to_local|5|40.0%|60.0%|0.0%|
|north_to_west|5|40.0%|60.0%|0.0%|
|outer_to_south|5|0.0%|40.0%|60.0%|
|sano_east_to_south|5|80.0%|20.0%|0.0%|
|sano_north_through|5|0.0%|100.0%|0.0%|
|sano_north_to_west|5|60.0%|40.0%|0.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|100.0%|0.0%|
|sano_south_to_west|5|60.0%|40.0%|0.0%|
|sano_west_to_north|5|0.0%|100.0%|0.0%|
|sano_west_to_south|5|40.0%|60.0%|0.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|100.0%|0.0%|
|south_to_local|5|0.0%|100.0%|0.0%|
|south_to_west|5|0.0%|100.0%|0.0%|
|west_through|5|100.0%|0.0%|0.0%|
|west_to_local|5|80.0%|20.0%|0.0%|

</details>

<details><summary>R0-33-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|60.0%|0.0%|
|east_to_north|5|60.0%|40.0%|0.0%|
|east_to_south|5|60.0%|40.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|20.0%|60.0%|20.0%|
|north_to_local|5|20.0%|20.0%|60.0%|
|north_to_west|5|20.0%|80.0%|0.0%|
|outer_to_south|5|60.0%|40.0%|0.0%|
|sano_east_to_south|5|80.0%|20.0%|0.0%|
|sano_north_through|5|100.0%|0.0%|0.0%|
|sano_north_to_west|5|40.0%|60.0%|0.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|60.0%|40.0%|0.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|100.0%|0.0%|
|south_to_local|5|0.0%|100.0%|0.0%|
|south_to_west|5|0.0%|100.0%|0.0%|
|west_through|5|20.0%|80.0%|0.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

<details><summary>RAMP-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|0.0%|100.0%|0.0%|
|east_to_north|1|0.0%|0.0%|100.0%|
|east_to_south|1|0.0%|0.0%|100.0%|
|north_through|1|100.0%|0.0%|0.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|0.0%|100.0%|
|sano_north_through|1|0.0%|100.0%|0.0%|
|sano_north_to_west|1|0.0%|0.0%|100.0%|
|sano_south_through|1|100.0%|0.0%|0.0%|
|sano_south_to_east|1|0.0%|0.0%|100.0%|
|sano_south_to_west|1|0.0%|100.0%|0.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|100.0%|0.0%|0.0%|
|south_to_east|1|0.0%|100.0%|0.0%|
|south_to_local|1|0.0%|100.0%|0.0%|
|south_to_west|1|0.0%|100.0%|0.0%|
|west_through|1|100.0%|0.0%|0.0%|
|west_to_local|1|0.0%|0.0%|100.0%|

</details>

<details><summary>RAMP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|60.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|80.0%|20.0%|0.0%|
|north_through|5|60.0%|20.0%|20.0%|
|north_to_east|5|0.0%|100.0%|0.0%|
|north_to_local|5|0.0%|100.0%|0.0%|
|north_to_west|5|0.0%|100.0%|0.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|20.0%|80.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|0.0%|100.0%|
|sano_south_through|5|80.0%|0.0%|20.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|80.0%|20.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|80.0%|20.0%|0.0%|
|south_to_east|5|0.0%|80.0%|20.0%|
|south_to_local|5|0.0%|80.0%|20.0%|
|south_to_west|5|0.0%|60.0%|40.0%|
|west_through|5|0.0%|20.0%|80.0%|
|west_to_local|5|0.0%|20.0%|80.0%|

</details>

<details><summary>ROUTE100-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|40.0%|20.0%|40.0%|
|east_to_north|5|80.0%|20.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|100.0%|0.0%|0.0%|
|north_to_east|5|0.0%|20.0%|80.0%|
|north_to_local|5|0.0%|40.0%|60.0%|
|north_to_west|5|0.0%|20.0%|80.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|0.0%|40.0%|60.0%|
|sano_north_through|5|0.0%|20.0%|80.0%|
|sano_north_to_west|5|0.0%|60.0%|40.0%|
|sano_south_through|5|100.0%|0.0%|0.0%|
|sano_south_to_east|5|0.0%|0.0%|100.0%|
|sano_south_to_west|5|0.0%|40.0%|60.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|60.0%|40.0%|
|south_to_local|5|0.0%|60.0%|40.0%|
|south_to_west|5|0.0%|60.0%|40.0%|
|west_through|5|80.0%|20.0%|0.0%|
|west_to_local|5|0.0%|60.0%|40.0%|

</details>

<details><summary>ZIP-11-10000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|1|100.0%|0.0%|0.0%|
|east_to_north|1|0.0%|0.0%|100.0%|
|east_to_south|1|0.0%|0.0%|100.0%|
|north_through|1|0.0%|100.0%|0.0%|
|north_to_east|1|0.0%|100.0%|0.0%|
|north_to_local|1|0.0%|100.0%|0.0%|
|north_to_west|1|0.0%|100.0%|0.0%|
|outer_to_south|1|0.0%|100.0%|0.0%|
|sano_east_to_south|1|0.0%|0.0%|100.0%|
|sano_north_through|1|100.0%|0.0%|0.0%|
|sano_north_to_west|1|0.0%|0.0%|100.0%|
|sano_south_through|1|0.0%|0.0%|100.0%|
|sano_south_to_east|1|0.0%|0.0%|100.0%|
|sano_south_to_west|1|0.0%|0.0%|100.0%|
|sano_west_to_north|1|0.0%|0.0%|100.0%|
|sano_west_to_south|1|0.0%|0.0%|100.0%|
|south_through|1|0.0%|0.0%|100.0%|
|south_to_east|1|0.0%|0.0%|100.0%|
|south_to_local|1|0.0%|0.0%|100.0%|
|south_to_west|1|0.0%|0.0%|100.0%|
|west_through|1|100.0%|0.0%|0.0%|
|west_to_local|1|0.0%|0.0%|100.0%|

</details>

<details><summary>ZIP-11-200000 경로별 평가</summary>

|경로|횟수|완주|충돌|시간 초과|
|---|---:|---:|---:|---:|
|east_through|5|0.0%|60.0%|40.0%|
|east_to_north|5|100.0%|0.0%|0.0%|
|east_to_south|5|100.0%|0.0%|0.0%|
|north_through|5|20.0%|20.0%|60.0%|
|north_to_east|5|0.0%|0.0%|100.0%|
|north_to_local|5|0.0%|0.0%|100.0%|
|north_to_west|5|0.0%|80.0%|20.0%|
|outer_to_south|5|100.0%|0.0%|0.0%|
|sano_east_to_south|5|100.0%|0.0%|0.0%|
|sano_north_through|5|0.0%|0.0%|100.0%|
|sano_north_to_west|5|0.0%|20.0%|80.0%|
|sano_south_through|5|80.0%|0.0%|20.0%|
|sano_south_to_east|5|100.0%|0.0%|0.0%|
|sano_south_to_west|5|0.0%|20.0%|80.0%|
|sano_west_to_north|5|0.0%|40.0%|60.0%|
|sano_west_to_south|5|0.0%|40.0%|60.0%|
|south_through|5|100.0%|0.0%|0.0%|
|south_to_east|5|0.0%|0.0%|100.0%|
|south_to_local|5|0.0%|0.0%|100.0%|
|south_to_west|5|0.0%|0.0%|100.0%|
|west_through|5|0.0%|0.0%|100.0%|
|west_to_local|5|0.0%|0.0%|100.0%|

</details>

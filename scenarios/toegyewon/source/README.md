# OSM 원자료

© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
OSM 도로 데이터와 그 데이터베이스 파생물에는 ODbL 조건이 적용됩니다. 저장소의 기존 코드 라이선스를 변경하는 선언은 아닙니다.

- `area.osm.xml`: Overpass에서 받은 도로 way와 참조 node 원본. 모델보다 넓은 범위입니다.
- `north.osm.xml`: 북쪽 OPEN 앞의 way 86198728. 공식 OSM API의 full 응답입니다.
- `provenance.json`: 조회 URL/쿼리, 수집일, SHA-256, 사용자 설계도 식별 해시.

생성기는 이 두 원본을 함께 읽고 선택된 구간만 사용합니다. 네트워크 없이 재생성할 수 있습니다. 이 파일을 새 OSM 데이터로 교체하면 연결과 경계 교점이 달라질 수 있으므로 `validate`를 다시 실행해야 합니다. 잘못된 교점이나 끊긴 way 연결은 생성 단계에서 실패하도록 했습니다.

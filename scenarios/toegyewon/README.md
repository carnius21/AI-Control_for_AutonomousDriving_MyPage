# 퇴계원IC 독립 시나리오

[설계·실행·검증·가정값·Fork 반영 안내](../../docs/toegyewon/README.md)

[교통량 단계·Route 비중 조절·실제 비교 결과](../../docs/toegyewon/traffic.md)

[버스·AV 실행 방법, 코드 분석 및 검증 결과](../../docs/toegyewon/bus_av.md)

[POMDP 데이터 수집, JSONL/NPZ 형식, 재개·검증 및 실제 결과](../../docs/toegyewon/data_collection.md)

저장소 루트에서:

```bash
python toegyewon.py build
python toegyewon.py validate
python toegyewon.py gui
python toegyewon.py gui --traffic high
python toegyewon.py compare
python toegyewon.py gui --bus-ratio 0.1 --av sumo
python toegyewon.py validate-bus
python toegyewon.py validate-av
```

필수 추가 도구는 이 폴더의 `requirements.txt`에 있습니다. OSM 원자료는 `source/`에 포함되어 있어 네트워크 없이 재생성 가능합니다. 생성물과 상세 로그는 기본 `build/`에 쓰며 기존 고속도로 XML은 사용하지 않습니다.

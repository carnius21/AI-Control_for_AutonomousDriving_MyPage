# HV 높은 트래픽 + 입구 준비 거리 조정

`run.sumocfg`를 SUMO-GUI에서 열어 실행한다. 1시간에 15,000대 유입.
트래픽 파일은 `../hv_high15000`과 동일하고, 북쪽 남행은 원본 대비 +300m, 나머지 짧은 입구는 +100~250m다.
[맵 변경 및 before/after](../../maps/toegyewon_entryprep/README.md).

검증 명령:
```
python -X utf8 -m utils.hv_high_traffic --modes mainline_high --seeds 7201 7202 7203 --entryprep --output results/my_entryprep_hour
python -X utf8 -m utils.hv_high_traffic --modes mainline_high --seeds 7301 7302 7303 --entryprep --duration 7200 --horizon 10800 --output results/my_entryprep_long
```

원본 프로필과 이전 연장 버전은 보존했다. AV 학습은 중단 상태다.

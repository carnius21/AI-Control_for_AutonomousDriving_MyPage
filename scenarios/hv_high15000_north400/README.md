# HV15,000대/h + 북쪽진입부400m연장

`run.sumocfg`를SUMO-GUI에서열어실행한다. 북쪽남행5차로만400m연장했으며,트래픽파일은`../hv_high15000`과동일하다. 1시간에15,000대투입. 원본시나리오는보존했다.

검증재현:
```
python -X utf8 -m utils.hv_high_traffic --modes mainline_high --seeds 7201 7202 7203 --north400 --output results/my_north400_hour
python -X utf8 -m utils.hv_high_traffic --modes mainline_high --seeds 7301 7302 7303 --north400 --duration 7200 --horizon 10800 --output results/my_north400_long
```

[맵변경설명](../../maps/toegyewon_north400/README.md),[수요구성](../hv_high15000/README.md).
AV학습은중단상태이며이파일을기존실험기에자동교체하지않았다.

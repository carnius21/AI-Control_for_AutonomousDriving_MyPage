# 퇴계원IC 경로 그림

[16개 경로 전체 콜라주](toegyewon-16-routes.png)

`route_01.png`부터 `route_16.png`는 개별 경로 이미지입니다. 번호는 `maps/toegyewon_only/manifest.json`의 경로와 대응합니다. 도로 중심선을 연결한 경로 안내 그림이며 실제 차량의 차로 변경 궤적이나 성능 결과를 뜻하지 않습니다.

원본: `maps/toegyewon_only/network.net.xml`, `maps/toegyewon_only/manifest.json`.

저장소 루트에서 `python -m utils.render_toegyewon_routes`로 재생성합니다. Pillow와 Windows 맑은 고딕 글꼴을 사용합니다. 다른 운영체제에서는 생성 도구의 글꼴 경로를 해당 환경에 맞게 지정해야 합니다.

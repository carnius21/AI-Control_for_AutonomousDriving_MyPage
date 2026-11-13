"""Open the current OSM review map. Use --legacy only to reproduce the old hand-shaped map.

Rebuild current map: python -m utils.rebuild_osm_map
PPO/data collection remain paused pending route/observation migration.
"""
import argparse
import os
import subprocess

from env.road_config import ROAD, EGO, TRAFFIC
from env.mdp_config import SIMULATION
from env import road_builder
# sumo_env를 import하면 SUMO_HOME 자동 감지 로직이 함께 실행된다
from env.sumo_env import SumoHighwayEnv  # noqa: F401  (자동 감지 목적의 import)
from sumolib import checkBinary

BASE = os.path.dirname(os.path.abspath(__file__))


def print_summary():
    """현재 road_config 내용을 표로 요약 출력."""
    print("─" * 46)
    print(" 현재 도로 설정 (env/road_config.py)")
    print("─" * 46)
    print(f"  도로 길이      : {ROAD['length']} m")
    print(f"  차선 수        : {ROAD['num_lanes']}")
    print(f"  제한속도       : {ROAD['speed_limit']} m/s "
          f"(~ {float(ROAD['speed_limit']) * 3.6:.0f} km/h)")
    print(f"  배경 교통량    : {TRAFFIC['vehs_per_hour']} 대/시간")
    print(f"  배경차 최고속도: {TRAFFIC['max_speed']} m/s")
    print(f"  ego 가속/감속  : +{EGO['accel']} / -{EGO['decel']} m/s²")
    print("─" * 46)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="도로 구조를 GUI로 확인")
    parser.add_argument("--netedit", action="store_true",
                        help="sumo-gui 대신 netedit(도로 편집기)로 열기")
    parser.add_argument("--nogui", action="store_true",
                        help="화면 없이 설정 검증만 (GUI 없는 환경용)")
    parser.add_argument("--seconds", type=int, default=120,
                        help="--nogui 검증 시 시뮬레이션 길이(초). 기본 120초. "
                             "(GUI 모드는 시간 제한 없이 사용자가 직접 제어)")
    parser.add_argument("--legacy", action="store_true", help="과거 수작업 맵 재현 (학습 재개 아님)")
    parser.add_argument("--rebuild", action="store_true", help="첨부 OSM으로 현재 맵 재생성")
    args = parser.parse_args()
    if not args.legacy:
        from utils.rebuild_osm_map import build, DEST
        cfg = DEST / "review.sumocfg"
        if args.rebuild or not cfg.exists(): build()
        print("첨부 OSM 기반 현재 검토 맵. 학습/데이터 수집은 중단 상태입니다.")
        if args.netedit:
            command=[checkBinary("netedit"), str(DEST / "network.net.xml")]
        elif args.nogui:
            command=[checkBinary("sumo"), "-c", str(cfg), "--begin", "0", "--end", "0", "--no-step-log", "true"]
        else:
            command=[checkBinary("sumo-gui"), "-c", str(cfg)]
        raise SystemExit(subprocess.run(command).returncode)


    # 1) road_config 기준으로 SUMO 파일 (재)생성 — 수정사항이 즉시 반영된다
    sumocfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    net_file = os.path.join(BASE, "env", "sumo", "highway.net.xml")
    print(f"도로 생성 완료: {sumocfg}")
    print_summary()

    # 2) 요청한 모드로 열기
    if args.netedit:
        # netedit: SUMO에 포함된 도로망 편집기. 노드/엣지/차선을 시각적으로 확인.
        print("netedit 실행 중... (창을 닫으면 종료)")
        subprocess.run([checkBinary("netedit"), net_file])

    elif args.nogui:
        # 화면 없이 짧게 돌려서 "설정이 유효하고 차가 실제로 투입되는지"만 검증
        result = subprocess.run(
            [checkBinary("sumo"), "-c", sumocfg,
             "--step-length", str(SIMULATION["step_length"]),
             "--end", str(args.seconds),
             "--no-warnings", "true", "--no-step-log", "true",
             "--duration-log.statistics", "true"],   # 종료 시 차량 통계 출력
            capture_output=True, text=True)
        # SUMO의 통계 요약(투입/도착 차량 수 등)을 그대로 보여준다
        print(result.stderr.strip() or result.stdout.strip())
        print("설정 검증 OK" if result.returncode == 0 else "설정 오류!")

    else:
        # sumo-gui: 도로를 "정적으로" 띄운다.
        #   --start, --quit-on-end, --end 를 모두 주지 않는 것이 핵심:
        #     --start 없음      → 자동 재생 안 함. 창이 뜨면 도로만 보이고,
        #                         사용자가 ▶(플레이) 버튼을 눌러야 차가 움직인다.
        #     --quit-on-end 없음 → 시뮬레이션이 끝나도 창이 저절로 닫히지 않는다.
        #     --end 없음        → 시간 제한 없음. 원하는 만큼 돌려볼 수 있다.
        #   --delay 100 : 재생 시 스텝당 100ms (0이면 눈으로 못 따라갈 만큼 빠름).
        #                 GUI 상단 Delay 입력칸에서 실행 중에도 바꿀 수 있다.
        print("sumo-gui 실행 중...")
        print("  · 창이 뜨면 도로만 보입니다. ▶(플레이) 버튼을 눌러야 차가 움직입니다.")
        print(f"  · 확대: env/mdp_config.py의 gui_zoom={SIMULATION['gui_zoom']}")
        print("  · 속도 조절: 상단 Delay(ms) 값을 조정 (크게 = 느리게)")
        print("  · 종료하려면 창을 닫으세요.")
        subprocess.run(
            [checkBinary("sumo-gui"), "-c", sumocfg,
             "--step-length", str(SIMULATION["step_length"]),
             "--delay", str(SIMULATION["gui_delay"])])

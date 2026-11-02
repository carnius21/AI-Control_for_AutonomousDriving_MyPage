"""퇴계원IC 독립 시나리오 생성, 주행, 검증. 기존 고속도로는 변경하지 않는다."""

import argparse
import json
import subprocess
from pathlib import Path

from scenarios.toegyewon.network import HERE, binary, build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["build", "run", "gui", "validate", "validate-bus", "validate-av", "compare", "plot"])
    p.add_argument("--output", type=Path, default=HERE / "build")
    p.add_argument("--config", type=Path, default=HERE / "config.json")
    p.add_argument("--traffic", choices=["low", "medium", "high"])
    p.add_argument("--weave-factor", type=float, help="Weave route weight multiplier; 1 = no boost")
    p.add_argument("--demand-scale", type=float, help="Total background demand multiplier")
    p.add_argument("--seed", type=int)
    p.add_argument("--bus-ratio", type=float, help="Replace this fraction of background slots with buses (0..1)")
    p.add_argument("--av", choices=["sumo", "ppo"], help="Add one red AV; sumo is a non-learning baseline")
    p.add_argument("--av-route", help="One of the 12 route IDs (config default: pink)")
    p.add_argument("--av-depart", type=float)
    p.add_argument("--observation", choices=["route", "legacy"], help="43 route-aware or 31 highway-layout features")
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--policy-activation", choices=["relu", "tanh", "elu"])
    args = p.parse_args()
    overrides = {key: value for key, value in {
        "profile": args.traffic, "weave_factor": args.weave_factor,
        "scale": args.demand_scale,
    }.items() if value is not None}
    av_overrides = {key: value for key, value in {
        "route": args.av_route, "depart": args.av_depart, "observation": args.observation,
        "policy_activation": args.policy_activation,
    }.items() if value is not None}
    if args.av:
        av_overrides.update(enabled=True, controller=args.av)
    cfg = build(args.output, args.config, overrides, args.seed, args.bus_ratio, av_overrides)
    manifest = json.loads((cfg.parent / "manifest.json").read_text(encoding="utf-8"))
    if args.command in ["run", "gui"]:
        av = manifest["config"].get("av", {})
        if av.get("enabled") and (args.command == "run" or av.get("controller") == "ppo"):
            from scenarios.toegyewon.policy import run_av

            run_av(cfg.parent, manifest, args.command == "gui", args.checkpoint)
            return
        gui_options = []
        if args.command == "gui":
            gui_options = ["--start", "false", "--quit-on-end", "false",
                           "--tripinfo-output", str(cfg.parent / "gui.trips.xml"),
                           "--tripinfo-output.write-unfinished", "true",
                           "--lanechange-output", str(cfg.parent / "gui.lanechanges.xml"),
                           "--fcd-output", str(cfg.parent / "gui.fcd.xml"),
                           "--fcd-output.acceleration", "true"]
        subprocess.run(
            [
                binary("sumo-gui" if args.command == "gui" else "sumo"),
                "-c",
                str(cfg),
                *gui_options,
            ],
            check=True,
        )
    elif args.command == "validate":
        from scenarios.toegyewon.validate import validate

        validate(cfg.parent, manifest)
    elif args.command == "compare":
        from scenarios.toegyewon.validate import compare

        compare(cfg.parent, manifest)
    elif args.command == "validate-bus":
        from scenarios.toegyewon.validate_bus import validate_buses

        validate_buses(cfg.parent, manifest)
    elif args.command == "validate-av":
        from scenarios.toegyewon.validate_av import validate_av

        validate_av(cfg.parent, manifest)
    elif args.command == "plot":
        from scenarios.toegyewon.plot import plot

        plot(cfg.parent, manifest)
    else:
        print(cfg)


if __name__ == "__main__":
    main()

"""퇴계원IC 독립 시나리오 생성, 주행, 검증. 기존 고속도로는 변경하지 않는다."""

import argparse
import json
import subprocess
from pathlib import Path

from scenarios.toegyewon.network import HERE, binary, build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["build", "run", "gui", "validate", "plot"])
    p.add_argument("--output", type=Path, default=HERE / "build")
    p.add_argument("--config", type=Path, default=HERE / "config.json")
    args = p.parse_args()
    cfg = build(args.output, args.config)
    manifest = json.loads((cfg.parent / "manifest.json").read_text(encoding="utf-8"))
    if args.command in ["run", "gui"]:
        subprocess.run(
            [
                binary("sumo-gui" if args.command == "gui" else "sumo"),
                "-c",
                str(cfg),
                
            ],
            check=True,
        )
    elif args.command == "validate":
        from scenarios.toegyewon.validate import validate

        validate(cfg.parent, manifest)
    elif args.command == "plot":
        from scenarios.toegyewon.plot import plot

        plot(cfg.parent, manifest)
    else:
        print(cfg)


if __name__ == "__main__":
    main()

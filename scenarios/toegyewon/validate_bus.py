"""Real SUMO bus regression and mixed-traffic experiments, without control."""

import copy
import json
from pathlib import Path

import sumolib

from .validate import check_structure, run


def vehicle(vid, route, kind="HV", depart=0):
    return dict(id=vid, route=route, type=kind, depart=depart,
                departLane="0" if route == "pink" else "2",
                color="1,0.65,0" if kind == "BUS" else "0,0.9,0.2")


def validate_buses(out, manifest):
    out = Path(out)
    (out / "bus_validation.json").unlink(missing_ok=True)
    structure = check_structure(out, manifest)
    net = sumolib.net.readNet(str(out / "toegyewon.net.xml"))
    assert all(l.allows("bus") and l.allows("passenger") for e in net.getEdges() for l in e.getLanes())
    base = copy.deepcopy(manifest)
    base["config"].setdefault("buses", {}).update(ratio=0, route_ratios={})
    base["config"].setdefault("av", {})["enabled"] = False
    p = run(out, base, "bus_solo_pink", [vehicle("bus_pink", "pink", "BUS")])
    g = run(out, base, "bus_solo_green", [vehicle("bus_green", "green", "BUS")])
    car_p = run(out, base, "bus_reference_pink", [vehicle("car_pink", "pink")])
    car_g = run(out, base, "bus_reference_green", [vehicle("car_green", "green")])
    cases = {"bus_solo_pink": p, "bus_solo_green": g}
    # Synchronize using measured free-flow travel time; no commands after departure.
    for label, first, second, a, b in [
        ("bus_pink_car_green", "bus_pink", "car_green", p, car_g),
        ("car_pink_bus_green", "car_pink", "bus_green", car_p, g),
    ]:
        offset = a["weave"][first]["enter"] - b["weave"][second]["enter"]
        vehicles = [vehicle(first, "pink", "BUS" if first.startswith("bus") else "HV", max(0, -offset)),
                    vehicle(second, "green", "BUS" if second.startswith("bus") else "HV", max(0, offset))]
        cases[label] = run(out, base, label, vehicles)
    for label, ratio in [("bus_none", 0), ("bus_mix", .1)]:
        mixed = copy.deepcopy(base)
        mixed["config"]["buses"]["ratio"] = ratio
        cases[label] = run(out, mixed, label, None, True, 600)
    failures = []
    for name, result in cases.items():
        m = result["metrics"]
        if m["completion_rate"] != 1 or m["remaining"] or m["collision_events"] or m["teleport_starts"] or m["warnings"]:
            failures.append(name + ": incomplete / collision / teleport / warnings")
        for v, item in m["vehicles"].items():
            if item["type"] == "BUS" and item["route"] in ("pink", "green"):
                if not (item["arrived"] and item["weave_lane_changes"] and item["weave_exit_reached"] and item["route_edges_in_order"]):
                    failures.append(name + ": bus route / weave lane change failed: " + v)
        forbidden = manifest["config"].get("no_lane_change_edges", [])
        if any(c["from"].rsplit("_", 1)[0] in forbidden for c in result["lane_changes"]):
            failures.append(name + ": prohibited lane change")
        print(name, "types", m["by_type"], "car follows bus in weave", round(m["weave_car_follow_bus_seconds"], 2), flush=True)
    report = {"config": manifest["config"], "structure": structure,
              "cases": {n: r["metrics"] for n, r in cases.items()}, "failures": failures,
              "safety_findings": {n: {"hard_braking_episodes": r["metrics"]["hard_braking_episodes"],
                                       "min_acceleration_mps2": r["metrics"]["min_acceleration_mps2"]}
                                  for n, r in cases.items() if r["metrics"]["hard_braking_episodes"]}}
    (out / "bus_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures:
        raise RuntimeError("; ".join(failures))
    return report

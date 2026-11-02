"""AV route, interaction and safety-gate tests using actual SUMO episodes."""

import copy
import json
from pathlib import Path

from .av_env import ToegyewonEnv
from .validate import run
from .validate_bus import vehicle


def validate_av(out, manifest):
    out = Path(out)
    (out / "av_validation.json").unlink(missing_ok=True)
    cases = {}

    def episode(name, route, ratio=0, depart=0, background=True, other=None, external=False):
        case = copy.deepcopy(manifest)
        case["config"].setdefault("buses", {}).update(ratio=ratio, route_ratios={})
        case["config"].setdefault("av", {}).update(enabled=True, route=route, depart=depart, observation="route")
        ego = case["config"]["av"].get("id", "av_toegyewon")
        vehicles = None if other is None and background else [vehicle(ego, route, "AV", depart), *(other or [])]
        if vehicles:
            vehicles[0]["color"] = "1,0,0"
        env = ToegyewonEnv(out, case, "external" if external else "sumo", name, vehicles, background)
        try:
            obs, _ = env.reset()
            while not env.done:
                assert env.observation_space.contains(obs), (name, "invalid observation")
                assert all(n["gap"] >= 0 if n["leader"] else n["gap"] <= 0
                           for n in env.last_state["neighbors"]), (name, "neighbor direction sign")
                # Deliberately request left even when no lane/gap is available.
                # This is an action-gate probe, NOT a trained policy.
                obs, _, _, _, _ = env.step([1, 1] if external else None)
            result = env.finish()
        finally:
            env.close()
        cases[name] = result
        print(name, result["status"], "all", result["arrived"], "/", result["planned"],
              "bus neighbor seconds", round(result["av_weave_bus_neighbor_seconds"], 2),
              "rejected", result["rejected_actions"], flush=True)
        return result

    solo_p = episode("av_empty_pink", "pink", background=False)
    solo_g = episode("av_empty_green", "green", background=False)
    episode("av_hv_pink", "pink", depart=0)
    episode("av_hv_green", "green", depart=17.4)
    episode("av_mix_pink", "pink", ratio=.1, depart=90)
    episode("av_mix_green", "green", ratio=.1, depart=103)

    base = copy.deepcopy(manifest)
    base["config"].setdefault("av", {})["enabled"] = False
    bp = run(out, base, "av_bus_reference_pink", [vehicle("bus_pink", "pink", "BUS")])
    bg = run(out, base, "av_bus_reference_green", [vehicle("bus_green", "green", "BUS")])
    offset_g = bp["weave"]["bus_pink"]["enter"] - solo_g["av_weave_enter"]
    offset_p = solo_p["av_weave_enter"] - bg["weave"]["bus_green"]["enter"]
    episode("av_green_bus_pink", "green", depart=max(0, offset_g), background=False,
            other=[vehicle("bus_pink", "pink", "BUS", max(0, -offset_g))])
    episode("av_pink_bus_green", "pink", depart=max(0, -offset_p), background=False,
            other=[vehicle("bus_green", "green", "BUS", max(0, offset_p))])
    episode("av_unsafe_request_probe", "green", depart=max(0, offset_g), background=False, external=True,
            other=[vehicle("bus_pink", "pink", "BUS", max(0, -offset_g))])
    failures = []
    for name, r in cases.items():
        if (not r["av_arrived"] or r["collisions"] or r["teleports"] or r["warnings"]
                or r["remaining"] or r["planned"] != r["arrived"] or not r["av_weave_lane_changes"]):
            failures.append(name + ": arrival / safety / lane-change regression")
    if not any(r["av_weave_car_neighbor_seconds"] > 0 for r in cases.values()):
        failures.append("No AV/car interaction observed")
    if not all(cases[n]["av_weave_bus_neighbor_seconds"] > 0 for n in ("av_green_bus_pink", "av_pink_bus_green")):
        failures.append("No AV/bus interaction in a synchronized case")
    if not cases["av_unsafe_request_probe"]["rejected_actions"].get("insufficient_gap"):
        failures.append("Unsafe lane-change probe did not exercise gap rejection")
    report = {"config": manifest["config"], "cases": cases, "failures": failures,
              "safety_findings": {n: {"hard_braking_episodes": r["av_hard_braking_episodes"],
                                       "min_acceleration_mps2": r["av_min_acceleration"]}
                                  for n, r in cases.items() if r["av_hard_braking_episodes"]},
              "learned_policy_tested": False,
              "note": "SUMO baselines and an explicit safety-gate probe; no learned policy performance claim."}
    (out / "av_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures:
        raise RuntimeError("; ".join(failures))
    return report

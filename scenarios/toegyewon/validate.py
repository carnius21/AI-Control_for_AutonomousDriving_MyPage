"""실제 SUMO 주행 로그와 차로 연결로 검증한다. 강제 차량 제어는 사용하지 않는다."""

import csv
import copy
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import sumolib
import traci
import traci.constants as tc

from .network import binary, write_demand
from .traffic import demand_plan, route_features


def run(out, manifest, name, vehicles, background=False, limit=360):
    out = Path(out)
    cfg = write_demand(out, manifest, vehicles, background, name)
    args = [
        binary("sumo"),
        "-c",
        str(cfg),
        "--no-step-log",
        "true",
        "--tripinfo-output",
        str(out / (name + ".trips.xml")),
        "--tripinfo-output.write-unfinished",
        "true",
        "--lanechange-output",
        str(out / (name + ".lanechanges.xml")),
        "--collision-output",
        str(out / (name + ".collisions.xml")),
        "--error-log",
        str(out / (name + ".errors.log")),
    ]
    log = (out / (name + ".sumo.log")).open("w", encoding="utf-8")
    try:
        traci.start(args, label=name, stdout=log)
    except Exception:
        log.close()
        raise
    c = traci.getConnection(name)
    departed = []
    arrived = []
    collisions = []
    teleports = []
    weave = {}
    min_acc = {}
    samples = 0
    try:
        with (out / (name + ".trajectory.csv")).open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "time",
                    "vehicle",
                    "edge",
                    "lane",
                    "position",
                    "speed",
                    "acceleration",
                    "leader",
                    "gap",
                ]
            )
            while (
                c.simulation.getMinExpectedNumber() > 0
                and c.simulation.getTime() < limit
            ):
                c.simulationStep()
                t = c.simulation.getTime()
                new_vehicles = c.simulation.getDepartedIDList()
                departed.extend(new_vehicles)
                for v in new_vehicles:
                    c.vehicle.subscribe(v, (
                        tc.VAR_ROAD_ID, tc.VAR_LANE_ID, tc.VAR_LANEPOSITION,
                        tc.VAR_SPEED, tc.VAR_ACCELERATION, tc.VAR_LEADER,
                    ), parameters={tc.VAR_LEADER: ("d", 100.)})
                arrived.extend(c.simulation.getArrivedIDList())
                collisions.extend(c.simulation.getCollidingVehiclesIDList())
                teleports.extend(c.simulation.getStartingTeleportIDList())
                for v, data in c.vehicle.getAllSubscriptionResults().items():
                    edge = data[tc.VAR_ROAD_ID]
                    lane = data[tc.VAR_LANE_ID]
                    pos = data[tc.VAR_LANEPOSITION]
                    speed = data[tc.VAR_SPEED]
                    acc = data[tc.VAR_ACCELERATION]
                    leader = data[tc.VAR_LEADER]
                    if leader and not leader[0]:
                        leader = None
                    writer.writerow(
                        [t, v, edge, lane, pos, speed, acc, *(leader or ("", ""))]
                    )
                    samples += 1
                    if edge == "weave":
                        item = weave.setdefault(
                            v,
                            {
                                "enter": t,
                                "exit": t,
                                "lanes": [],
                                "min_acceleration": acc,
                                "leader_samples": 0,
                            },
                        )
                        item["exit"] = t
                        if lane not in item["lanes"]:
                            item["lanes"].append(lane)
                        item["min_acceleration"] = min(item["min_acceleration"], acc)
                        if leader and leader[0] in ("pink", "green"):
                            item["leader_samples"] += 1
                    min_acc[v] = min(min_acc.get(v, 0), acc)
            remaining = c.simulation.getMinExpectedNumber()
            end_time = c.simulation.getTime()
            active = list(c.vehicle.getIDList())
    finally:
        c.close()
        log.close()
    changes = [
        dict(e.attrib)
        for e in ET.parse(out / (name + ".lanechanges.xml")).findall("change")
    ]
    trips = [
        dict(e.attrib)
        for e in ET.parse(out / (name + ".trips.xml")).findall("tripinfo")
    ]
    result = {
        "config": manifest["config"],
        "background": background,
        "time_limit": limit,
        "departed": departed,
        "arrived": arrived,
        "remaining": remaining,
        "simulation_end": end_time,
        "active_at_end": active,
        "collisions": sorted(set(collisions)),
        "teleports": sorted(set(teleports)),
        "teleport_starts": len(teleports),
        "weave": weave,
        "lane_changes": changes,
        "trips": trips,
        "trajectory_samples": samples,
        "min_acceleration": min_acc,
    }
    result["metrics"] = summarize(out, manifest, name, result)
    (out / (name + ".result.json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def summarize(out, manifest, name, result):
    """Aggregate samples including unfinished vehicles; episodes are not step counts.

    A harsh braking episode starts below -4.5 m/s² (configurable), with a
    tolerance to exclude floating point noise at the normal HV decel value.
    Leader/overlap counts are interaction proxies, not proof of yielding.
    """
    out = Path(out)
    config = manifest["config"]
    settings = config.get("validation", {})
    threshold = float(settings.get("hard_braking_threshold", -4.5))
    stopped_speed = float(settings.get("stopped_speed", 0.1))
    if not threshold < 0 or stopped_speed < 0:
        raise ValueError("Invalid braking threshold or stopped speed")
    dt = config["step_length"]
    demand = ET.parse(out / (name + ".rou.xml"))
    vehicle_routes = {v.get("id"): v.get("route") for v in demand.findall("vehicle")}
    flow_routes = {f.get("id"): f.get("route") for f in demand.findall("flow")}
    vehicle_types = {v.get("id"): v.get("type", "HV") for v in demand.findall("vehicle")}
    flow_types = {f.get("id"): f.get("type", "HV") for f in demand.findall("flow")}
    planned_by_route = Counter(vehicle_routes.values())
    for f in demand.findall("flow"):
        # Also read original baseline XML, which used end + period.
        count = int(f.get("number")) if f.get("number") else math.ceil(
            (float(f.get("end")) - float(f.get("begin"))) / float(f.get("period")) - 1e-10
        )
        planned_by_route[f.get("route")] += count

    def route_of(v):
        return vehicle_routes.get(v) or flow_routes.get(v.rsplit(".", 1)[0], "unknown")

    def type_of(v):
        return vehicle_types.get(v) or flow_types.get(v.rsplit(".", 1)[0], "unknown")

    def origin(v):
        route = manifest["routes"].get(route_of(v), [])
        return "pink" if "pink_approach" in route else "green" if "green_approach" in route else None

    edges = defaultdict(lambda: {
        "samples": 0, "speed_sum": 0., "stopped_vehicle_seconds": 0.,
        "max_stopped_vehicles": 0, "min_acceleration": 0.,
        "hard_braking_episodes": 0,
    })
    harsh, harsh_vehicles, weave_harsh = {}, set(), set()
    harsh_count = 0
    weave_vehicles = set()
    time_groups = {}
    close_follow_seconds = cross_follow_seconds = 0.
    total_samples = 0
    speed_sum = 0.
    details = {}
    car_bus_follow_seconds = car_bus_brake_seconds = 0.
    with (out / (name + ".trajectory.csv")).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            t, v, edge = float(row["time"]), row["vehicle"], row["edge"]
            speed, acc = float(row["speed"]), float(row["acceleration"])
            detail = details.setdefault(v, {
                "type": type_of(v), "route": route_of(v), "visited_edges": [],
                "min_acceleration": 0., "weave_lanes": [], "bus_leader_seconds": 0.,
                "weave_enter": None, "weave_exit": None,
            })
            if not detail["visited_edges"] or detail["visited_edges"][-1] != edge:
                detail["visited_edges"].append(edge)
            detail["min_acceleration"] = min(detail["min_acceleration"], acc)
            if edge == "weave":
                if detail["weave_enter"] is None:
                    detail["weave_enter"] = t
                detail["weave_exit"] = t
                lane = row.get("lane", "")
                if lane not in detail["weave_lanes"]:
                    detail["weave_lanes"].append(lane)
                if row["leader"] and type_of(row["leader"]) == "BUS" and float(row["gap"]) <= 20:
                    detail["bus_leader_seconds"] += dt
                    if type_of(v) != "BUS":
                        car_bus_follow_seconds += dt
                        if acc < -.5:
                            car_bus_brake_seconds += dt
            item = edges[edge]
            item["samples"] += 1
            item["speed_sum"] += speed
            item["min_acceleration"] = min(item["min_acceleration"], acc)
            total_samples += 1
            speed_sum += speed
            frame = time_groups.setdefault(t, {"origins": set(), "weave": 0, "stopped": Counter()})
            if speed < stopped_speed:
                item["stopped_vehicle_seconds"] += dt
                frame["stopped"][edge] += 1
            braking = acc < threshold - 1e-6
            if braking:
                harsh_vehicles.add(v)
                if not harsh.get(v, False):
                    harsh_count += 1
                    item["hard_braking_episodes"] += 1
            harsh[v] = braking
            if edge == "weave":
                weave_vehicles.add(v)
                frame["weave"] += 1
                frame["origins"].add(origin(v))
                if braking:
                    weave_harsh.add(v)
                if row["leader"] and float(row["gap"]) <= 20:
                    close_follow_seconds += dt
                    if origin(v) and origin(row["leader"]) and origin(v) != origin(row["leader"]):
                        cross_follow_seconds += dt
    for frame in time_groups.values():
        for edge, count in frame["stopped"].items():
            edges[edge]["max_stopped_vehicles"] = max(edges[edge]["max_stopped_vehicles"], count)
    for item in edges.values():
        item["mean_speed_mps"] = item.pop("speed_sum") / item["samples"]
    changes = result["lane_changes"]
    weave_changes = [c for c in changes if c["from"].startswith("weave_") and c["to"].startswith("weave_")]
    trips = [t for t in result["trips"] if float(t["arrival"]) >= 0]
    departed, arrived = Counter(map(route_of, result["departed"])), Counter(map(route_of, result["arrived"]))
    planned = sum(planned_by_route.values())
    collision_events = len(ET.parse(out / (name + ".collisions.xml")).findall("collision"))
    warnings = (out / (name + ".errors.log")).read_text(encoding="utf-8").splitlines()
    for v, detail in details.items():
        detail["arrived"] = v in result["arrived"]
        detail["weave_lane_changes"] = [c for c in weave_changes if c["id"] == v]
        route = manifest["routes"].get(detail["route"], [])
        detail["route_edges_in_order"] = [e for e in detail["visited_edges"] if not e.startswith(":")] == route
        detail["weave_exit_reached"] = ("weave" in route and route[route.index("weave") + 1] in detail["visited_edges"])
    return {
        "planned": planned, "departed": len(result["departed"]), "arrived": len(result["arrived"]),
        "completion_rate": len(result["arrived"]) / planned if planned else 1.,
        "inserted_completion_rate": len(result["arrived"]) / len(result["departed"]) if result["departed"] else None,
        "not_inserted": planned - len(result["departed"]),
        "active_at_end": len(result.get("active_at_end", [])), "remaining": result["remaining"],
        "simulation_end": result.get("simulation_end"),
        "collision_events": collision_events, "collision_vehicles": len(result["collisions"]),
        "teleport_starts": result.get("teleport_starts", len(result["teleports"])), "teleport_enabled": False,
        "lane_changes": len(changes), "weave_lane_changes": len(weave_changes),
        "lane_change_reasons": dict(Counter(c["reason"] for c in changes)),
        "weave_changes_with_neighbor": sum(any(c.get(k, "None") != "None" for k in ("leaderGap", "followerGap")) for c in weave_changes),
        "weave_vehicles": len(weave_vehicles),
        "weave_lane_changes_per_vehicle": len(weave_changes) / len(weave_vehicles) if weave_vehicles else 0.,
        "weave_both_origins_seconds": sum({"pink", "green"} <= f["origins"] for f in time_groups.values()) * dt,
        "weave_peak_vehicles": max((f["weave"] for f in time_groups.values()), default=0),
        "weave_close_follow_vehicle_seconds": close_follow_seconds,
        "weave_cross_origin_follow_vehicle_seconds": cross_follow_seconds,
        "hard_braking_threshold_mps2": threshold,
        "hard_braking_episodes": harsh_count, "hard_braking_vehicles": len(harsh_vehicles),
        "hard_braking_episodes_per_100_departed": 100 * harsh_count / len(result["departed"]) if result["departed"] else 0.,
        "weave_hard_braking_vehicles": len(weave_harsh),
        "min_acceleration_mps2": min(result["min_acceleration"].values(), default=0.),
        "mean_speed_mps": speed_sum / total_samples if total_samples else None,
        "mean_completed_depart_delay_s": sum(float(t["departDelay"]) for t in trips) / len(trips) if trips else None,
        "max_completed_depart_delay_s": max((float(t["departDelay"]) for t in trips), default=0.),
        "mean_completed_time_loss_s": sum(float(t["timeLoss"]) for t in trips) / len(trips) if trips else None,
        "edges": dict(edges),
        "routes": {r: {"planned": n, "departed": departed[r], "arrived": arrived[r]} for r, n in planned_by_route.items()},
        "warnings": warnings,
        "vehicles": details,
        "by_type": {kind: {"departed": sum(type_of(v) == kind for v in result["departed"]),
                           "arrived": sum(type_of(v) == kind for v in result["arrived"])}
                    for kind in sorted(set(map(type_of, result["departed"])))},
        "weave_car_follow_bus_seconds": car_bus_follow_seconds,
        "weave_car_brake_behind_bus_seconds": car_bus_brake_seconds,
    }


def check_structure(out, manifest):
    net = sumolib.net.readNet(str(Path(out) / "toegyewon.net.xml"))
    actual = set()
    for e in net.getEdges():
        for outgoing, cs in e.getOutgoing().items():
            for c in cs:
                actual.add(
                    (
                        e.getID(),
                        outgoing.getID(),
                        c.getFromLane().getIndex(),
                        c.getToLane().getIndex(),
                    )
                )
    assert actual == {tuple(x) for x in manifest["connections"]}, (
        "Unexpected/missing lane connections"
    )
    for e in net.getEdges():
        for lane in e.getLanes():
            assert all(p[2] == 0 for p in lane.getShape3D()), "Nonzero z"
    for rid, route in manifest["routes"].items():
        for a, b in itertools.pairwise(route):
            assert net.getEdge(b) in net.getEdge(a).getOutgoing(), rid
    # A source-lane path cannot reach its destination without a weave lane change.
    assert ("pink_approach", "weave", 0, 3) in actual
    assert ("green_approach", "weave", 2, 2) in actual
    assert not any(
        a == "weave" and i == 3 and b == "east_curve" for a, b, i, j in actual
    )
    assert not any(
        a == "weave" and i == 2 and b == "upper_loop" for a, b, i, j in actual
    )
    assert manifest["routes"]["pink"][2] == manifest["routes"]["green"][2] == "weave"
    xml = ET.parse(Path(out) / "toegyewon.net.xml")
    for edge in manifest["config"].get("no_lane_change_edges", []):
        lanes = xml.findall(f".//edge[@id='{edge}']/lane")
        assert lanes and all(
            lane.get("changeLeft") == "emergency"
            and lane.get("changeRight") == "emergency"
            for lane in lanes
        ), edge
    return {
        "edges": len(net.getEdges()),
        "lane_connections": len(actual),
        "routes": len(manifest["routes"]),
        "weave_length_m": net.getEdge("weave").getLength(),
        "z_zero": True,
        "exact_connections": True,
        "two_route_specific_lane_changes_required": True,
    }


def validate(out, manifest):
    Path(out, "validation.json").unlink(missing_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    structure = check_structure(out, manifest)
    pink = {
        "id": "pink",
        "route": "pink",
        "depart": 0,
        "departLane": "0",
        "color": "1,0.15,0.7",
    }
    green = {
        "id": "green",
        "route": "green",
        "depart": 0,
        "departLane": "2",
        "color": "0,0.9,0.2",
    }
    single_p = run(out, manifest, "solo_pink", [pink])
    single_g = run(out, manifest, "solo_green", [green])
    # OSM lengths determine synchronization; only departure time changes, never vehicle actions.
    offset = single_p["weave"]["pink"]["enter"] - single_g["weave"]["green"]["enter"]
    pair = run(out, manifest, "pair", [pink, {**green, "depart": max(0, offset)}])
    route_vehicles = [
        {"id": "route_" + r, "route": r, "depart": i * 8, "departLane": "best"}
        for i, r in enumerate(manifest["routes"])
    ]
    low = run(out, manifest, "all_routes", route_vehicles)
    background = run(
        out,
        manifest,
        "background",
        [pink, {**green, "depart": max(0, offset)}],
        True,
        manifest["config"].get("validation", {}).get("time_limit", 600),
    )
    results = {
        "solo_pink": single_p,
        "solo_green": single_g,
        "pair": pair,
        "all_routes": low,
        "background": background,
    }
    failures = []
    for name, result in results.items():
        expected = {
            v["id"]
            for v in (
                [pink]
                if name == "solo_pink"
                else [green]
                if name == "solo_green"
                else route_vehicles
                if name == "all_routes"
                else [pink, green]
            )
        }
        if not expected <= set(result["arrived"]):
            failures.append(name + ": required vehicles did not arrive")
        if (result["remaining"] or set(result["departed"]) != set(result["arrived"])
                or result["metrics"]["completion_rate"] != 1):
            failures.append(name + ": vehicles left unfinished")
        if result["collisions"] or result["teleports"]:
            failures.append(name + ": collision/teleport")
        forbidden = manifest["config"].get("no_lane_change_edges", [])
        if any(
            change["from"].rsplit("_", 1)[0] in forbidden
            for change in result["lane_changes"]
        ):
            failures.append(name + ": lane change on prohibited edge")
        if (Path(out) / (name + ".errors.log")).read_text(encoding="utf-8").strip():
            failures.append(name + ": SUMO warnings/errors; inspect log")
    for name, result in [
        ("solo_pink", single_p),
        ("solo_green", single_g),
        ("pair", pair),
    ]:
        ids = ["pink", "green"] if name == "pair" else [name[5:]]
        for v in ids:
            if not any(
                x["id"] == v
                and x["from"].startswith("weave_")
                and x["to"].startswith("weave_")
                for x in result["lane_changes"]
            ):
                failures.append(name + ": no recorded weave lane change for " + v)
    p = pair["weave"]["pink"]
    g = pair["weave"]["green"]
    overlap = min(p["exit"], g["exit"]) - max(p["enter"], g["enter"])
    interaction = {
        "shared_time_seconds": max(0, overlap),
        "pink_pair_min_acceleration": p["min_acceleration"],
        "green_pair_min_acceleration": g["min_acceleration"],
        "green_observed_pink_as_leader": g["leader_samples"] > 0,
        "pink_solo_min_acceleration": single_p["weave"]["pink"]["min_acceleration"],
        "green_solo_min_acceleration": single_g["weave"]["green"]["min_acceleration"],
    }
    if (
        overlap <= 0
        or not g["leader_samples"]
        or min(p["min_acceleration"], g["min_acceleration"]) >= -0.5
    ):
        failures.append(
            "pair: interaction not evidenced by overlap, leader gap and deceleration"
        )
    summary = {
        "started_utc": started,
        "python": platform.python_version(),
        "sumo": subprocess.check_output(
            [binary("sumo"), "--version"], text=True
        ).splitlines()[0],
        "config": manifest["config"],
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).parent / "source").glob("*.osm.xml")
        },
        "interaction": interaction,
        "structure": structure,
        "green_depart_for_pair": round(max(0, offset), 3),
        "failures": failures,
        "cases": {
            k: {
                "departed": len(v["departed"]),
                "arrived": len(v["arrived"]),
                "remaining": v["remaining"],
                "collisions": v["collisions"],
                "teleports": v["teleports"],
                "weave": v["weave"],
                "lane_changes": v["lane_changes"],
                "metrics": v["metrics"],
            }
            for k, v in results.items()
        },
    }
    Path(out, "validation.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
    for name, result in results.items():
        print(
            name,
            "arrived",
            len(result["arrived"]),
            "/",
            len(result["departed"]),
            "collision",
            len(result["collisions"]),
            "teleport",
            len(result["teleports"]),
        )
    if failures:
        raise RuntimeError("; ".join(failures))
    return summary


def compare(out, manifest):
    """Same network, horizon, seed and HV model; vary demand only.

    Report overload as a finding, and never hide it by teleporting vehicles.
    A run with collisions, unfinished demand or SUMO warnings fails the command
    after all cases and their diagnostics have been written.
    """
    out = Path(out)
    for filename in ("traffic_comparison.json", "traffic_comparison.csv"):
        (out / filename).unlink(missing_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    structure = check_structure(out, manifest)
    base_traffic = manifest["config"]["traffic"]
    profiles = base_traffic.get("profiles", {
        "low": {"period": 30}, "medium": {"period": 12}, "high": {"period": 6},
    })
    cases = {
        "baseline": {"period": 30, "end": base_traffic["end"]},
        "low": {**base_traffic, "profiles": profiles, "profile": "low"},
        "medium_uniform": {**base_traffic, "profiles": profiles, "profile": "medium", "weave_factor": 1},
        "medium": {**base_traffic, "profiles": profiles, "profile": "medium"},
        "high": {**base_traffic, "profiles": profiles, "profile": "high"},
    }
    results, failures = {}, []
    for name, traffic in cases.items():
        case = copy.deepcopy(manifest)
        case["config"]["traffic"] = traffic
        result = run(out, case, "compare_" + name, None, True,
                     case["config"].get("validation", {}).get("time_limit", 600))
        metrics = result["metrics"]
        forbidden = case["config"].get("no_lane_change_edges", [])
        if metrics["completion_rate"] != 1 or result["remaining"]:
            failures.append(name + ": unfinished demand / insertion backlog")
        if metrics["collision_events"] or result["collisions"] or result["teleports"]:
            failures.append(name + ": collision / teleport")
        if any(c["from"].rsplit("_", 1)[0] in forbidden for c in result["lane_changes"]):
            failures.append(name + ": prohibited lane change")
        if metrics["warnings"]:
            failures.append(name + ": SUMO warnings/errors; inspect log")
        results[name] = {"traffic": traffic, "demand": demand_plan(case["config"], case["routes"]), "metrics": metrics}
        print(f"{name}: arrived {metrics['arrived']}/{metrics['planned']}, "
              f"lane changes {metrics['lane_changes']} (weave {metrics['weave_lane_changes']}), "
              f"hard braking {metrics['hard_braking_episodes']}", flush=True)
    report = {
        "started_utc": started, "python": platform.python_version(),
        "sumo": subprocess.check_output([binary("sumo"), "--version"], text=True).splitlines()[0],
        "config": manifest["config"], "structure": structure,
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__).parent / "source").glob("*.osm.xml")},
        "route_features": route_features(manifest["routes"], manifest["edges"]),
        "cases": results, "failures": failures,
        "definitions": {
            "completion_rate": "arrived / all planned, including vehicles never inserted",
            "mean_speed_mps": "vehicle-time weighted samples, including stopped and unfinished vehicles",
            "hard_braking": "episode starts at acceleration < threshold - 1e-6; not a sample count",
            "weave_both_origins_seconds": "time with both pink-approach and green-approach traffic on weave",
            "weave_cross_origin_follow_vehicle_seconds": "weave vehicle with other-approach leader within 20m; proxy, not proof of yielding",
            "teleport": "disabled (-1); zero teleports alone is not evidence of no gridlock",
            "completed_trip_metrics": "depart delay and time loss exclude unfinished trips; also inspect not_inserted and remaining",
        },
    }
    (out / "traffic_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    columns = ["planned", "departed", "arrived", "completion_rate", "not_inserted", "remaining",
               "lane_changes", "weave_lane_changes", "weave_both_origins_seconds",
               "weave_cross_origin_follow_vehicle_seconds", "hard_braking_episodes",
               "hard_braking_episodes_per_100_departed", "weave_hard_braking_vehicles",
               "min_acceleration_mps2", "mean_speed_mps", "mean_completed_depart_delay_s",
               "mean_completed_time_loss_s", "collision_events", "teleport_starts"]
    with (out / "traffic_comparison.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case"] + columns)
        writer.writeheader()
        for name, result in results.items():
            writer.writerow({"case": name, **{k: result["metrics"][k] for k in columns}})
    if failures:
        raise RuntimeError("; ".join(failures))
    return report

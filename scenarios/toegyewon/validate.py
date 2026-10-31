"""실제 SUMO 주행 로그와 차로 연결로 검증한다. 강제 차량 제어는 사용하지 않는다."""

import csv
import hashlib
import itertools
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import sumolib
import traci

from .network import binary, write_demand


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
                departed.extend(c.simulation.getDepartedIDList())
                arrived.extend(c.simulation.getArrivedIDList())
                collisions.extend(c.simulation.getCollidingVehiclesIDList())
                teleports.extend(c.simulation.getStartingTeleportIDList())
                for v in c.vehicle.getIDList():
                    edge = c.vehicle.getRoadID(v)
                    lane = c.vehicle.getLaneID(v)
                    pos = c.vehicle.getLanePosition(v)
                    speed = c.vehicle.getSpeed(v)
                    acc = c.vehicle.getAcceleration(v)
                    leader = c.vehicle.getLeader(v, 100)
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
        "departed": departed,
        "arrived": arrived,
        "remaining": remaining,
        "collisions": sorted(set(collisions)),
        "teleports": sorted(set(teleports)),
        "weave": weave,
        "lane_changes": changes,
        "trips": trips,
        "trajectory_samples": samples,
        "min_acceleration": min_acc,
    }
    (out / (name + ".result.json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


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
        600,
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
        if result["remaining"] or set(result["departed"]) != set(result["arrived"]):
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

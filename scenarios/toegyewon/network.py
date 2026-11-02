"""OSM 형상 + 손필기 범위를 명시적으로 조합하는 별도 도로 생성기.

기존 env/road_builder.py와 같이 plain XML -> netconvert -> sumocfg를 사용한다.
기존 직선 고속도로 파일은 읽거나 덮어쓰지 않는다. 모든 높이는 0이다.
"""

import itertools
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from pyproj import Transformer
from sumolib import checkBinary

from .traffic import demand_plan, route_features
from .vehicles import background_demand, bus_ratio, write_types

HERE = Path(__file__).resolve().parent


def binary(name):
    # pip Eclipse SUMO 설치 및 별도 SUMO 설치 모두 지원한다.
    try:
        import sumo

        os.environ.setdefault("SUMO_HOME", sumo.SUMO_HOME)
    except ImportError:
        pass
    return checkBinary(name)


def write_xml(root, path):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


class Source:
    def __init__(self):
        self.nodes, self.ways = {}, {}
        for path in sorted((HERE / "source").glob("*.osm.xml")):
            root = ET.parse(path)
            for n in root.findall("node"):
                self.nodes[n.get("id")] = (float(n.get("lon")), float(n.get("lat")))
            for w in root.findall("way"):
                self.ways[w.get("id")] = (
                    [n.get("ref") for n in w.findall("nd")],
                    {t.get("k"): t.get("v") for t in w.findall("tag")},
                )

    def part(self, way, start=None, end=None):
        ids, _ = self.ways[str(way)]
        a = ids.index(str(start)) if start is not None else 0
        b = ids.index(str(end)) + 1 if end is not None else len(ids)
        assert a < b
        return [self.nodes[n] for n in ids[a:b]]


def cut(points, axis, value, keep_after):
    """기존 OSM 선분과 OPEN 좌표의 교점을 보간하여 자른다 (임의 연장 없음)."""
    for i, (a, b) in enumerate(itertools.pairwise(points)):
        if (
            min(a[axis], b[axis]) <= value <= max(a[axis], b[axis])
            and a[axis] != b[axis]
        ):
            t = (value - a[axis]) / (b[axis] - a[axis])
            p = tuple(a[k] + t * (b[k] - a[k]) for k in (0, 1))
            return [p] + points[i + 1 :] if keep_after else points[: i + 1] + [p]
    raise ValueError(
        f"OPEN boundary does not intersect source geometry: {axis}={value}"
    )


def layout(config):
    src = Source()
    proj = Transformer.from_crs("EPSG:4326", config["projection"], always_xy=True)
    ox, oy = proj.transform(*config["origin_lon_lat"])
    edges = {}

    def chain(*parts):
        points = []
        for part in parts:
            p = src.part(part) if isinstance(part, int) else src.part(*part)
            if points:
                assert points[-1] == p[0], (parts, points[-1], p[0])
                p = p[1:]
            points.extend(p)
        return points

    def add(name, a, b, ways, pts=None, lanes=None, speed=None, note=None):
        tags = [src.ways[str(w)][1] for w in ways]
        assert all(t.get("oneway") == "yes" for t in tags), name
        points = pts if pts is not None else chain(*ways)
        lane_tags = {t["lanes"] for t in tags if "lanes" in t}
        if lanes is None:
            lanes = (
                int(next(iter(lane_tags)))
                if len(lane_tags) == 1
                else config["assumed_ramp_lanes"]
            )
        speed_tags = {t["maxspeed"] for t in tags if "maxspeed" in t}
        if speed is None:
            speed = (
                float(next(iter(speed_tags)))
                if len(speed_tags) == 1
                else config["assumed_ramp_speed_kmh"]
            )
        xy = [(proj.transform(*p)[0] - ox, proj.transform(*p)[1] - oy) for p in points]
        edges[name] = {
            "id": name,
            "start": a,
            "end": b,
            "ways": ways,
            "lonlat": points,
            "shape": xy,
            "lanes": lanes,
            "speed_kmh": speed,
            "tags": tags,
            "note": note,
        }

    bounds = config["boundaries"]
    # 북쪽 본선의 선행 way는 official OSM API로 별도 수집한다.
    north_way = next(
        int(w)
        for w, (ns, t) in src.ways.items()
        if ns[-1] == "498837378" and t.get("highway") == "motorway"
    )
    add(
        "N_in",
        "N_IN",
        "N_SPLIT",
        [north_way],
        cut(src.part(north_way), 1, bounds["north_lat"], True),
    )
    add("main_s_bridge", "N_SPLIT", "SB_DROP", [86198725, 86198709])
    add("main_s", "SB_DROP", "S_MERGE", [37927509])
    add(
        "S_out",
        "S_MERGE",
        "S_OUT",
        [206426298],
        cut(src.part(206426298), 1, bounds["south_lat"], False),
    )
    add(
        "S_in",
        "S_IN",
        "S_SPLIT",
        [52873356],
        cut(src.part(52873356), 1, bounds["south_lat"], True),
    )
    add(
        "main_n",
        "S_SPLIT",
        "N_MERGE",
        [844484878],
        src.part(844484878, end=12994833390),
    )
    add(
        "main_n_after",
        "N_MERGE",
        "NB_BRIDGE",
        [844484878],
        src.part(844484878, start=12994833390),
    )
    add("main_n_bridge", "NB_BRIDGE", "NB_END", [86198722])
    add(
        "N_out",
        "NB_END",
        "N_OUT",
        [86198708],
        cut(src.part(86198708), 1, bounds["north_lat"], False),
    )
    add(
        "pink_approach",
        "N_SPLIT",
        "WEAVE_IN",
        [37927508, 86198720, 170059988, 170059996, 170059995],
        lanes=1,
    )
    add("green_approach", "S_SPLIT", "WEAVE_IN", [37927512, 170059991])
    add("weave", "WEAVE_IN", "WEAVE_OUT", [170059994])
    add("east_curve", "WEAVE_OUT", "E_SPLIT", [1063527748])
    add(
        "E_ramp_out",
        "E_SPLIT",
        "E_RAMP_OUT",
        [169728835],
        cut(src.part(169728835), 0, bounds["east_lon"], False),
    )
    add("east_join", "E_SPLIT", "E_MERGE", [797789364], lanes=1)
    add("upper_loop", "WEAVE_OUT", "W_MERGE", [844484876, 86198717, 170059992], lanes=1)
    # 주을천교 오른쪽의 손필기 평면화: W 분기를 경계 내부로 옮긴다.
    trunk = src.part(781184662)
    west_start = cut(trunk, 0, bounds["west_lon"], True)
    before = cut(west_start, 0, config["relocated_west_diverge_lon"], False)
    after = cut(trunk, 0, config["relocated_west_diverge_lon"], True)
    add(
        "W_in",
        "W_IN",
        "W_SPLIT",
        [781184662],
        before,
        lanes=config["assumed_trunk_lanes"],
        speed=70,
    )
    east_end = src.nodes["7461635551"]
    upto = after[: after.index(east_end) + 1]
    add(
        "east_main",
        "W_SPLIT",
        "E_MERGE",
        [781184662],
        upto,
        lanes=config["assumed_trunk_lanes"],
        speed=70,
    )
    add(
        "E_main_out",
        "E_MERGE",
        "E_MAIN_OUT",
        [781184662],
        cut(src.part(781184662, start=7461635551), 0, bounds["east_lon"], False),
        lanes=config["assumed_trunk_lanes"],
        speed=70,
    )
    src.part(169929503)
    add(
        "E_in",
        "E_IN",
        "W_MERGE",
        [556956812, 169929503],
        cut(
            chain(556956812, (169929503, None, 1810880137)), 0, bounds["east_lon"], True
        ),
        lanes=config["assumed_trunk_lanes"],
        speed=70,
    )
    add(
        "W_out",
        "W_MERGE",
        "W_OUT",
        [169929503],
        cut(src.part(169929503, start=1810880137), 0, bounds["west_lon"], False),
        lanes=config["assumed_trunk_lanes"],
        speed=70,
    )
    ramp = [before[-1]] + src.part(170059993, start=1812112835)
    add(
        "west_turn",
        "W_SPLIT",
        "W_RAMP",
        [170059993],
        ramp,
        lanes=1,
        note="Sketch override: relocate diverge east of bridge within blue scope; retain downstream connectivity.",
    )
    add(
        "west_south",
        "W_RAMP",
        "W_RAMP_SPLIT",
        [544293888],
        src.part(544293888, end=498837707),
    )
    add("west_to_n", "W_RAMP_SPLIT", "N_MERGE", [37375274])
    add(
        "west_to_s",
        "W_RAMP_SPLIT",
        "S_MERGE",
        [544293888, 86198710, 170059989],
        chain((544293888, 498837707, None), 86198710, 170059989),
    )
    return edges


def connections(edges):
    result = []
    for a in edges.values():
        for b in edges.values():
            if a["end"] != b["start"]:
                continue
            key = (a["id"], b["id"])
            if key == ("pink_approach", "weave"):
                pairs = [(0, 3)]
            elif key == ("green_approach", "weave"):
                pairs = [(i, i) for i in range(3)]
            elif key == ("weave", "upper_loop"):
                pairs = [(3, 0)]
            elif key == ("weave", "east_curve"):
                pairs = [(i, i) for i in range(3)]
            elif key == ("main_s", "S_out"):
                pairs = [(i, i + 1) for i in range(3)]
            elif b["lanes"] == 1:
                pairs = [(0, 0)]
            else:
                pairs = [(i, min(i, b["lanes"] - 1)) for i in range(a["lanes"])]
            result.extend((a["id"], b["id"], i, j) for i, j in pairs)
    return result


def routes():
    north = ["N_in", "main_s_bridge", "main_s", "S_out"]
    nb = ["main_n", "main_n_after", "main_n_bridge", "N_out"]
    pink = ["N_in", "pink_approach", "weave"]
    green = ["S_in", "green_approach", "weave"]
    east = ["east_curve", "E_ramp_out"]
    join = ["east_curve", "east_join", "E_main_out"]
    loop = ["upper_loop", "W_out"]
    west = ["W_in", "west_turn", "west_south"]
    return {
        "N_S": north,
        "S_N": ["S_in"] + nb,
        "pink": pink + east,
        "N_E_main": pink + join,
        "N_W": pink + loop,
        "green": green + loop,
        "S_E_ramp": green + east,
        "S_E_main": green + join,
        "W_E": ["W_in", "east_main", "E_main_out"],
        "E_W": ["E_in", "W_out"],
        "W_N": west + ["west_to_n"] + nb[1:],
        "W_S": west + ["west_to_s", "S_out"],
    }


def build(output, config_path=None, traffic_overrides=None, seed=None, bus_share=None, av_overrides=None):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        Path(config_path or HERE / "config.json").read_text(encoding="utf-8")
    )
    config["traffic"].update(traffic_overrides or {})
    if seed is not None:
        config["seed"] = seed
    if bus_share is not None:
        config.setdefault("buses", {}).update(ratio=bus_share, route_ratios={})
    unknown = set(config.get("buses", {}).get("route_ratios", {})) - set(routes())
    if unknown:
        raise ValueError(f"Unknown bus routes: {sorted(unknown)}")
    for route in routes():
        bus_ratio(config, route)
    config.setdefault("av", {}).update(av_overrides or {})
    if config["av"].get("enabled") and config["av"].get("route", "green") not in routes():
        raise ValueError("AV route must be one of the 12 declared routes")
    plan = demand_plan(config, routes())
    edges = layout(config)
    links = connections(edges)
    nodes = ET.Element("nodes")
    positions = {}
    for e in edges.values():
        for key, p in [(e["start"], e["shape"][0]), (e["end"], e["shape"][-1])]:
            if key in positions:
                assert positions[key] == p, key
            positions[key] = p
    for key, (x, y) in positions.items():
        ET.SubElement(nodes, "node", id=key, x=str(x), y=str(y), z="0", type="priority")
    edg = ET.Element("edges")
    for e in edges.values():
        attrs = {
            "id": e["id"],
            "from": e["start"],
            "to": e["end"],
            "numLanes": str(e["lanes"]),
            "speed": str(e["speed_kmh"] / 3.6),
            "priority": str(3 if "main" in e["id"] else 2),
            "allow": "passenger bus",
            "shape": " ".join(f"{x:.3f},{y:.3f},0" for x, y in e["shape"]),
        }
        child = ET.SubElement(edg, "edge", attrs)
        if e["id"] in config.get("no_lane_change_edges", []) or any(
            t.get("change") == "no" for t in e["tags"]
        ):
            for i in range(e["lanes"]):
                ET.SubElement(
                    child,
                    "lane",
                    index=str(i),
                    changeLeft="emergency",
                    changeRight="emergency",
                )
    con = ET.Element("connections")
    for a, b, i, j in links:
        ET.SubElement(
            con,
            "connection",
            {"from": a, "to": b, "fromLane": str(i), "toLane": str(j)},
        )
    for root, name in [
        (nodes, "nodes.nod.xml"),
        (edg, "edges.edg.xml"),
        (con, "connections.con.xml"),
    ]:
        write_xml(root, out / name)
    cmd = [
        binary("netconvert"),
        "--node-files",
        str(out / "nodes.nod.xml"),
        "--edge-files",
        str(out / "edges.edg.xml"),
        "--connection-files",
        str(out / "connections.con.xml"),
        "--output-file",
        str(out / "toegyewon.net.xml"),
        "--no-turnarounds",
        "true",
        "--offset.disable-normalization",
        "true",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    (out / "netconvert.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    manifest = {
        "config": config,
        "edges": edges,
        "connections": links,
        "routes": routes(),
        "nodes": positions,
        "route_features": route_features(routes(), edges),
        "demand": plan,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_demand(out, manifest)
    return out / "toegyewon.sumocfg"


def write_demand(out, manifest, vehicles=None, background=True, stem="toegyewon"):
    out = Path(out)
    cfg = manifest["config"]
    root = ET.Element("routes")
    write_types(root, cfg)
    for name, route in manifest["routes"].items():
        ET.SubElement(root, "route", id=name, edges=" ".join(route))
    if vehicles is None:
        vehicles = [
            {
                "id": "pink",
                "route": "pink",
                "depart": cfg["test_vehicles"]["pink_depart"],
                "departLane": "0",
                "color": "1,0.15,0.7",
            },
            {
                "id": "green",
                "route": "green",
                "depart": cfg["test_vehicles"]["green_depart"],
                "departLane": "2",
                "color": "0,0.9,0.2",
            },
        ]
        av = cfg.get("av", {})
        if av.get("enabled"):
            vehicles.append({"id": av.get("id", "av_toegyewon"), "type": "AV",
                             "route": av.get("route", "green"), "depart": av.get("depart", 17.4),
                             "departLane": "best", "color": "1,0,0"})
    demand = []
    for vehicle in vehicles:
        attrs = {
            "type": "HV",
            "departSpeed": "max",
            **{k: str(v) for k, v in vehicle.items()},
        }
        demand.append((float(attrs["depart"]), ET.Element("vehicle", attrs)))
    if background:
        demand.extend(background_demand(cfg, demand_plan(cfg, manifest["routes"])))
    root.extend(v for _, v in sorted(demand, key=lambda x: x[0]))
    write_xml(root, out / (stem + ".rou.xml"))
    conf = ET.Element("configuration")
    inp = ET.SubElement(conf, "input")
    ET.SubElement(inp, "net-file", value="toegyewon.net.xml")
    ET.SubElement(inp, "route-files", value=stem + ".rou.xml")
    tim = ET.SubElement(conf, "time")
    ET.SubElement(tim, "step-length", value=str(cfg["step_length"]))
    proc = ET.SubElement(conf, "processing")
    for name, value in [
        ("lanechange.duration", cfg["lane_change_duration"]),
        ("time-to-teleport", -1),
        ("collision.action", "warn"),
    ]:
        ET.SubElement(proc, name, value=str(value))
    rand = ET.SubElement(conf, "random_number")
    ET.SubElement(rand, "seed", value=str(cfg["seed"]))
    write_xml(conf, out / (stem + ".sumocfg"))
    return out / (stem + ".sumocfg")

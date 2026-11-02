"""Adjustable vehicle assumptions and deterministic bus substitution."""

import math
import xml.etree.ElementTree as ET

HV = dict(vClass="passenger", carFollowModel="Krauss", laneChangeModel="LC2013",
          accel="2.6", decel="4.5", emergencyDecel="9", sigma="0", tau="1",
          minGap="2.5", length="5", speedFactor="1", speedDev="0")


def bus_ratio(config, route):
    buses = config.get("buses", {})
    value = float(buses.get("route_ratios", {}).get(route, buses.get("ratio", 0)))
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"Bus ratio for {route} must be in [0, 1]")
    return value


def write_types(root, config):
    ET.SubElement(root, "vType", id="HV", **HV)
    bus = config.get("buses", {}).get("vehicle", {})
    attrs = {**HV, "vClass": "bus", "guiShape": "bus", "color": "1,0.65,0",
             "length": 12, "width": 2.5, "accel": 1.2, "decel": 3.0,
             "emergencyDecel": 7, "tau": 1.5, "minGap": 3, "maxSpeed": 25,
             "lcStrategic": 1, "lcCooperative": 1, "lcSpeedGain": 1,
             "lcKeepRight": 1, **bus}
    if attrs["vClass"] != "bus":
        raise ValueError("BUS must use vClass=bus")
    for key in ("length", "width", "accel", "decel", "emergencyDecel", "tau", "maxSpeed", "minGap"):
        if not math.isfinite(float(attrs[key])) or float(attrs[key]) <= 0:
            raise ValueError(f"Invalid BUS {key}")
    ET.SubElement(root, "vType", id="BUS", **{k: str(v) for k, v in attrs.items()})
    ET.SubElement(root, "vType", id="AV", color="1,0,0", guiShape="passenger", **HV)


def background_demand(config, plan):
    """Replace evenly spaced slots; never add buses on top of the HV demand.

    Ratio zero preserves the old SUMO flows exactly. Nonzero ratios expand
    the same timetable into vehicles for reproducible per-route bus counts.
    """
    # Route-name validation belongs to network.build (disabled routes are valid).
    for flow in plan["flows"]:
        name, count = flow["route"], flow["planned"]
        ratio = bus_ratio(config, name)
        if not ratio:
            attrs = dict(id="flow_" + name, type="HV", route=name,
                         begin=str(flow["begin"]), number=str(count), period=str(flow["period"]),
                         departLane="best", departSpeed="max", color="0.6,0.65,0.7")
            yield flow["begin"], ET.Element("flow", attrs)
            continue
        buses = int(math.floor(count * ratio + .5))
        for i in range(count):
            is_bus = (i + 1) * buses // count > i * buses // count
            depart = flow["begin"] + i * flow["period"]
            attrs = dict(id=f"{'bus' if is_bus else 'flow'}_{name}.{i}",
                         type="BUS" if is_bus else "HV", route=name,
                         depart=str(depart), departLane="best", departSpeed="max",
                         color="1,0.65,0" if is_bus else "0.6,0.65,0.7")
            yield depart, ET.Element("vehicle", attrs)

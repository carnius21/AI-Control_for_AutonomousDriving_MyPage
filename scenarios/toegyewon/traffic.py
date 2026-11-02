"""Deterministic HV demand; weights change the mix, scale changes the total.

No vehicle commands: SUMO decides insertion, following and lane changing.
"""

import math


def route_features(routes, edges):
    """Classify by shared junctions (not by spatial crossings)."""
    incoming, outgoing = {}, {}
    for edge in edges.values():
        incoming.setdefault(edge["end"], set()).add(edge["id"])
        outgoing.setdefault(edge["start"], set()).add(edge["id"])
    result = {}
    for name, route in routes.items():
        junctions = [edges[e]["end"] for e in route[:-1]]
        result[name] = {
            "merges": [j for j in junctions if len(incoming[j]) > 1],
            "diverges": [j for j in junctions if len(outgoing[j]) > 1],
            "weave": "weave" in route,
            "weave_lane_change_required": (
                "weave" in route
                and (("pink_approach" in route and "east_curve" in route)
                     or ("green_approach" in route and "upper_loop" in route))
            ),
        }
    return result


def positive(value, name, zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (not zero and value == 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")
    return value


def demand_plan(config, routes):
    traffic = config["traffic"]
    profile = traffic.get("profile")
    if profile is None:  # Original {period, end} configs remain reproducible.
        period = positive(traffic["period"], "traffic.period")
    else:
        if profile not in traffic["profiles"]:
            raise ValueError(f"Unknown traffic profile: {profile}")
        period = positive(traffic["profiles"][profile]["period"], "profile.period")
    end = positive(traffic["end"], "traffic.end")
    scale = positive(traffic.get("scale", 1), "traffic.scale", zero=True)
    boost = positive(traffic.get("weave_factor", 1), "traffic.weave_factor", zero=True)
    custom = traffic.get("route_weights", {})
    unknown = set(custom) - set(routes)
    if unknown:
        raise ValueError(f"Unknown route weights: {sorted(unknown)}")
    weights = {
        name: positive(custom.get(name, 1), f"route_weights.{name}", zero=True)
        * (boost if "weave" in route else 1)
        for name, route in routes.items()
    }
    total_weight = sum(weights.values())
    if total_weight == 0 and scale > 0:
        raise ValueError("At least one route must have positive weight when scale > 0")
    total_rate = len(routes) * 3600 / period * scale
    flows = []
    for i, (name, weight) in enumerate(weights.items()):
        rate = total_rate * weight / total_weight if total_weight else 0
        begin = i * 2  # Preserve original departure phases and colored test pair.
        if not rate or begin >= end:
            continue
        interval = 3600 / rate
        flows.append({
            "route": name, "begin": begin, "end": end, "period": interval,
            "vehicles_per_hour": rate,
            "planned": math.ceil((end - begin) / interval - 1e-10),
        })
    return {
        "profile": profile or "legacy", "total_vehicles_per_hour": total_rate,
        "weave_share": sum(w for r, w in weights.items() if "weave" in routes[r])
        / total_weight if total_weight else 0,
        "planned_background": sum(f["planned"] for f in flows), "flows": flows,
    }

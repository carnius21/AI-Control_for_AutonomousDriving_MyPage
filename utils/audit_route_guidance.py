"""Compare route and lane guidance along the same SUMO-driven trajectories."""
import json
from pathlib import Path

import libsumo as sim

from env.navigation_clarity import second_constraint_features
from utils.mcw_train import ROUTES, load_network_metadata, prepare_scenario


def main():
    output = Path("results/jys2_nav_comparison_20261119")
    cfg = prepare_scenario("none", output)
    road, nav = load_network_metadata(cfg.parent / "network.net.xml", cfg.parent / "highway.rou.xml")
    results = {}
    for route in ["route_04", "route_14", *[r for r in ROUTES if r not in ("route_04", "route_14")]]:
        path = road["routes"][route]
        summary = dict(samples=0, route_disagreements=0, comparable=0, different_direction=0, arrived=False)
        sim.start(["sumo", "-c", str(cfg), "--seed", "11", "--no-step-log", "true"])
        try:
            sim.vehicle.add("probe", route, typeID="ego_type", departLane="0")
            with (output / (route + ".jsonl")).open("w") as stream:
                for _ in range(6000):
                    sim.simulationStep()
                    if "probe" in sim.simulation.getArrivedIDList():
                        summary["arrived"] = True
                        break
                    if "probe" not in sim.vehicle.getIDList():
                        continue
                    v = sim.vehicle
                    edge = v.getRoadID("probe")
                    if edge.startswith(":"):
                        continue
                    i = v.getRouteIndex("probe")
                    if i + 1 >= len(path):
                        continue
                    lane = v.getLaneIndex("probe")
                    lane_id = v.getLaneID("probe")
                    remain = sim.lane.getLength(lane_id) - v.getLanePosition("probe")
                    context = nav.query(path, i, lane, remain)
                    best = next(b for b in v.getBestLanes("probe") if b[0] == lane_id)
                    route_next = v.getRoute("probe")[i+1]
                    summary["samples"] += 1
                    summary["route_disagreements"] += int(route_next != path[i+1])
                    prep = context["prepare_targets"]
                    offset = nav.offset(lane, prep) if prep else None
                    if prep:
                        summary["comparable"] += 1
                        summary["different_direction"] += int((offset > 0) - (offset < 0) != (best[3] > 0) - (best[3] < 0))
                    record = dict(time=sim.simulation.getTime(), edge=edge, lane=lane, remaining=round(remain,2),
                                  custom_next=path[i+1], sumo_next=route_next, custom=context, prepare_offset=offset,
                                  second_constraint=second_constraint_features(nav,path,i,remain), sumo_best_offset=best[3],
                                  sumo_continuation=best[4])
                    stream.write(json.dumps(record) + "\n")
        finally:
            sim.close()
        results[route] = summary
    (output / "summary.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))


if __name__ == "__main__":
    main()

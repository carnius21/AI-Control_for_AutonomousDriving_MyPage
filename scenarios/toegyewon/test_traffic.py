"""Demand invariants; integration evidence is produced by toegyewon.py compare."""

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from .network import HERE, layout, routes
from .traffic import demand_plan, route_features
from .validate import summarize


class DemandTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
        self.routes = routes()

    def test_original_demand_is_reproducible(self):
        self.config["traffic"] = {"period": 30, "end": 180}
        plan = demand_plan(self.config, self.routes)
        self.assertEqual(plan["planned_background"], 72)
        self.assertEqual(plan["total_vehicles_per_hour"], 1440)
        self.assertEqual([f["begin"] for f in plan["flows"]], list(range(0, 24, 2)))
        self.assertTrue(all(f["period"] == 30 for f in plan["flows"]))

    def test_boost_preserves_total_rate(self):
        self.config["traffic"]["weave_factor"] = 1
        uniform = demand_plan(self.config, self.routes)
        self.config["traffic"]["weave_factor"] = 2
        focused = demand_plan(self.config, self.routes)
        self.assertEqual(uniform["total_vehicles_per_hour"], focused["total_vehicles_per_hour"])
        self.assertEqual(uniform["weave_share"], .5)
        self.assertAlmostEqual(focused["weave_share"], 2 / 3)
        self.assertAlmostEqual(sum(f["vehicles_per_hour"] for f in focused["flows"]), 3600)

    def test_route_weight_and_total_scale(self):
        self.config["traffic"]["route_weights"]["green"] = 0
        plan = demand_plan(self.config, self.routes)
        self.assertNotIn("green", [f["route"] for f in plan["flows"]])
        self.config["traffic"]["scale"] = 2
        self.assertEqual(demand_plan(self.config, self.routes)["total_vehicles_per_hour"], 2 * plan["total_vehicles_per_hour"])
        self.config["traffic"]["scale"] = 0
        self.assertEqual(demand_plan(self.config, self.routes)["flows"], [])

    def test_invalid_controls_fail_early(self):
        for key, value in [("scale", -1), ("weave_factor", float("nan")),
                           ("end", 0), ("profile", "typo"),
                           ("route_weights", {"typo": 2}),
                           ("route_weights", {r: 0 for r in self.routes})]:
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.config)
                config["traffic"][key] = value
                with self.assertRaises(ValueError):
                    demand_plan(config, self.routes)

    def test_topological_route_classification(self):
        features = route_features(self.routes, layout(self.config))
        self.assertEqual({r for r, f in features.items() if f["weave"]},
                         {"pink", "N_E_main", "N_W", "green", "S_E_ramp", "S_E_main"})
        self.assertEqual({r for r, f in features.items() if f["weave_lane_change_required"]},
                         {"pink", "N_E_main", "green"})
        self.assertEqual(features["W_E"]["merges"], ["E_MERGE"])
        self.assertEqual(features["W_E"]["diverges"], ["W_SPLIT"])

    def test_metrics_count_episodes_and_uninserted_demand(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "sample.rou.xml").write_text(
                '<routes><vehicle id="a" route="pink"/>'
                '<vehicle id="b" route="green"/>'
                '<flow id="waiting" route="N_S" number="1"/></routes>', encoding="utf-8")
            (out / "sample.collisions.xml").write_text('<collisions/>', encoding="utf-8")
            (out / "sample.errors.log").write_text('', encoding="utf-8")
            with (out / "sample.trajectory.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["time", "vehicle", "edge", "speed", "acceleration", "leader", "gap"])
                for t, acc in [(0.2, -5), (0.4, -5), (0.6, -4.50000000000001), (0.8, -5)]:
                    writer.writerow([t, "a", "weave", 0, acc, "b", 3])
                    writer.writerow([t, "b", "weave", 10, 0, "", ""])
            result = {
                "departed": ["a", "b"], "arrived": ["b"], "remaining": 2,
                "active_at_end": ["a"], "simulation_end": .8,
                "collisions": [], "teleports": [], "lane_changes": [], "trips": [],
                "min_acceleration": {"a": -5, "b": 0},
            }
            metrics = summarize(out, {"config": self.config, "routes": self.routes}, "sample", result)
            self.assertEqual(metrics["hard_braking_episodes"], 2)
            self.assertEqual(metrics["hard_braking_vehicles"], 1)
            self.assertAlmostEqual(metrics["completion_rate"], 1 / 3)
            self.assertEqual(metrics["not_inserted"], 1)
            self.assertEqual(metrics["active_at_end"], 1)
            self.assertEqual(metrics["mean_speed_mps"], 5)
            self.assertAlmostEqual(metrics["weave_both_origins_seconds"], .8)
            self.assertAlmostEqual(metrics["weave_cross_origin_follow_vehicle_seconds"], .8)


if __name__ == "__main__":
    unittest.main()

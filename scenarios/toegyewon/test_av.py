"""Mixed-demand invariants and checkpoint compatibility; no policy training."""

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from utils.networks import HybridActorCritic, GaussianActorCritic
from .network import HERE, routes
from .traffic import demand_plan
from .vehicles import background_demand, bus_ratio
from .policy import load_ppo


class MixedDemandTests(unittest.TestCase):
    def test_bus_substitution_preserves_schedule_and_count(self):
        config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
        plan = demand_plan(config, routes())
        config["buses"]["ratio"] = .1
        actual = list(background_demand(config, plan))
        self.assertEqual(len(actual), plan["planned_background"])
        expected = sorted((f["route"], round(f["begin"] + j * f["period"], 9))
                          for f in plan["flows"] for j in range(f["planned"]))
        self.assertEqual(sorted((v.get("route"), round(t, 9)) for t, v in actual), expected)
        self.assertEqual(sum(v.get("type") == "BUS" for _, v in actual), 18)
        self.assertTrue(any(v.get("type") == "BUS" and v.get("route") == "pink" for _, v in actual))
        self.assertTrue(any(v.get("type") == "BUS" and v.get("route") == "green" for _, v in actual))
        config["buses"]["ratio"] = 0
        self.assertTrue(all(v.tag == "flow" and v.get("type") == "HV" for _, v in background_demand(config, plan)))

    def test_route_override_and_invalid_ratio(self):
        cfg = {"buses": {"ratio": .1, "route_ratios": {"pink": .5}}}
        self.assertEqual(bus_ratio(cfg, "pink"), .5)
        self.assertEqual(bus_ratio(cfg, "green"), .1)
        for bad in (-.1, 1.1, float("nan")):
            cfg["buses"]["ratio"] = bad
            with self.assertRaises(ValueError):
                bus_ratio(cfg, "green")


class PolicyAdapterTests(unittest.TestCase):
    def test_legacy_dimension_requires_explicit_legacy_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "untrained_fixture.pt"
            torch.save(HybridActorCritic(31, (8, 8), "relu").state_dict(), path)
            with self.assertRaisesRegex(ValueError, "31 != environment 43"):
                load_ppo(path, 43, "toegyewon-route43-v1")
            agent = load_ppo(path, 31, "highway-layout31-adapter-v1")
            self.assertEqual(agent.predict(np.zeros(31, dtype=np.float32)).shape, (2,))
            self.assertFalse(agent.checkpoint_info["schema_verified"])

    def test_route_checkpoint_schema_and_architecture(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "untrained_fixture.pt"
            payload = {"algorithm": "ppo", "observation_schema": "toegyewon-route43-v1",
                       "activation": "tanh", "state_dict": HybridActorCritic(43, (8, 8), "tanh").state_dict()}
            torch.save(payload, path)
            agent = load_ppo(path, 43, "toegyewon-route43-v1")
            self.assertTrue(agent.checkpoint_info["schema_verified"])
            self.assertTrue(np.isfinite(agent.predict(np.zeros(43, dtype=np.float32))).all())
            payload["observation_schema"] = "wrong-semantics"
            torch.save(payload, path)
            with self.assertRaisesRegex(ValueError, "schema"):
                load_ppo(path, 43, "toegyewon-route43-v1")

    def test_wrong_action_dimension_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "untrained_fixture.pt"
            torch.save(GaussianActorCritic(31, 3, (8, 8), "relu").state_dict(), path)
            with self.assertRaisesRegex(ValueError, "2 actions"):
                load_ppo(path, 31, "highway-layout31-adapter-v1")


if __name__ == "__main__":
    unittest.main()

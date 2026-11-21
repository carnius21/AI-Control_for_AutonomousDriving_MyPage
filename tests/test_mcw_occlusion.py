import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from utils.mcw_train import McwEnv, VEHICLE_TYPE_COLORS, _segment_intersects_obb, prepare_scenario


class McwOcclusionTests(unittest.TestCase):
    def _make_stub_env(self, truck_rate=1.0, bus_rate=1.0, delivery_rate=0.5) -> McwEnv:
        env = McwEnv.__new__(McwEnv)
        env.occlusion = True
        env.occ_truck_rate = truck_rate
        env.occ_bus_rate = bus_rate
        env.occ_delivery_rate = delivery_rate
        env._occ_sensor_mask = False
        env._occ_subscribed = True
        env._occ_sensor = (0.0, 0.0)
        env._occ_boxes = []
        env._ctx_vehicles = {}
        env._occluded_cache = {}
        env._colored_delivery_ids = set()
        env.ego_id = "ego"
        env.visibility = 120.0
        return env

    def test_segment_intersects_obb_blocks_behind_and_diagonal(self):
        # Truck centered at (0, 20), heading North (+y): ux=0, uy=1, rx=1, ry=0, length=9 (hl=4.5), width=2.5 (hw=1.25)
        box = (0.0, 20.0, 0.0, 1.0, 1.0, 0.0, 4.5, 1.25)
        # Vehicle directly behind truck in same lane at (0, 35) -> occluded
        self.assertTrue(_segment_intersects_obb(0.0, 0.0, 0.0, 35.0, *box))
        # Adjacent diagonal vehicle at (3.5, 50) (ray passes at y=20 -> x = 3.5 * 20/50 = 1.4 > 1.25? No, try x=2.8 -> 1.12 <= 1.25) -> occluded
        self.assertTrue(_segment_intersects_obb(0.0, 0.0, 2.8, 50.0, *box))
        # Vehicle clearly ahead/beside at (3.5, 20) -> visible
        self.assertFalse(_segment_intersects_obb(0.0, 0.0, 3.5, 20.0, *box))
        # Vehicle closer than truck at (0, 10) -> visible
        self.assertFalse(_segment_intersects_obb(0.0, 0.0, 0.0, 10.0, *box))

    def test_differential_occlusion_rates(self):
        env = self._make_stub_env(truck_rate=1.0, bus_rate=1.0, delivery_rate=0.5)
        self.assertTrue(env._is_opaque_occluder("veh_t1", "truck"))
        self.assertTrue(env._is_opaque_occluder("veh_b1", "bus"))
        self.assertFalse(env._is_opaque_occluder("veh_p1", "passenger"))
        opaque_count = sum(1 for i in range(400) if env._is_opaque_occluder(f"flow_{i}", "delivery"))
        self.assertGreater(opaque_count, 160)
        self.assertLess(opaque_count, 240)
        # Deterministic per vehicle ID across steps
        first = env._is_opaque_occluder("flow_42", "delivery")
        self.assertEqual(first, env._is_opaque_occluder("flow_42", "delivery"))

    def test_is_occluded_respects_sensor_mask_and_self(self):
        env = self._make_stub_env()
        env._occ_boxes = [("bus_0", 3.5, 20.0, 0.0, 1.0, 1.0, 0.0, 6.0, 1.25)]
        # Target car in lane +2 behind the +1 bus: ray from (0,0) to (7.0, 42.0) passes through (3.5, 21.0)
        with patch("utils.mcw_train.traci") as mock_traci:
            tc = mock_traci.constants
            tc.VAR_POSITION = 66
            tc.VAR_ANGLE = 67
            tc.VAR_LENGTH = 68
            env._ctx_vehicles = {
                "bus_0": {tc.VAR_POSITION: (3.5, 26.0), tc.VAR_ANGLE: 0.0, tc.VAR_LENGTH: 12.0},
                "car_far": {tc.VAR_POSITION: (7.0, 44.4), tc.VAR_ANGLE: 0.0, tc.VAR_LENGTH: 4.8},
            }
            # Outside _get_obs (_occ_sensor_mask=False), ground-truth safety sees it
            self.assertFalse(env._is_occluded("car_far"))
            # Inside _get_obs (_occ_sensor_mask=True), car_far is occluded, bus_0 is visible
            env._occ_sensor_mask = True
            self.assertFalse(env._is_occluded("bus_0"))
            self.assertTrue(env._is_occluded("car_far"))

    def test_prepare_scenario_color_by_type_strips_flow_color(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = prepare_scenario("high_real_ratio", Path(tmp), color_by_type=True)
            rou = ET.parse(str(cfg.parent / "highway.rou.xml")).getroot()
            for flow in rou.findall("flow"):
                self.assertIsNone(flow.get("color"))
            vtypes = {vt.get("id"): vt.get("color") for vt in rou.findall("vType")}
            self.assertEqual(vtypes["truck_idm"], VEHICLE_TYPE_COLORS["truck_idm"])
            self.assertEqual(vtypes["bus_idm"], VEHICLE_TYPE_COLORS["bus_idm"])
            self.assertEqual(vtypes["delivery_idm"], VEHICLE_TYPE_COLORS["delivery_idm"])
            self.assertEqual(vtypes["ego_type"], VEHICLE_TYPE_COLORS["ego_type"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from env.navigation_clarity import ClarityEnv
from utils.mcw_train import McwEnv


class McwAgenda2Tests(unittest.TestCase):
    def _make_stub_env(self, agenda2: bool) -> McwEnv:
        env = McwEnv.__new__(McwEnv)
        env.use_route_conn = True
        env.agenda2 = agenda2
        env.obs_noise = False
        env.visibility = 120.0
        env.vmax = 27.78
        env.obs_offsets = (2, 1, 0, -1, -2)
        env.ego_id = "ego"
        env.episode_route = "r_test"
        env.routes = {"r_test": ["e0", "e1", "e2"]}
        return env

    def test_agenda2_masks_target_lane_and_lookahead_slots(self):
        env = self._make_stub_env(agenda2=True)
        raw = np.arange(47, dtype=np.float32) + 1.0
        with patch.object(ClarityEnv, "_get_obs", return_value=raw), patch("utils.mcw_train.traci") as mock_traci:
            mock_traci.vehicle.getIDList.return_value = ["ego"]
            obs = env._get_obs()
        self.assertEqual(obs.shape, (47,))
        self.assertTrue(np.allclose(obs[31:34], 0.0))
        self.assertTrue(np.allclose(obs[37:47], 0.0))
        self.assertTrue(np.allclose(obs[21:31], raw[21:31]))
        self.assertTrue(np.allclose(obs[34:37], raw[34:37]))

    def test_agenda2_multihop_lane_connectivity_detects_two_hop_dead_end(self):
        lengths = {"e0_0": 200.0, "e0_1": 200.0, "e1_0": 67.0, "e1_1": 67.0, "e2_0": 85.0}
        links = {
            "e0_0": [("e1_0", False, True, False, ":j0_0", "M", "s", 0.0)],
            "e0_1": [("e1_1", False, True, False, ":j0_1", "M", "s", 0.0)],
            "e1_0": [("e2_0", False, True, False, ":j1_0", "M", "s", 0.0)],
            "e1_1": [],
        }

        def setup_mock(mock_traci):
            mock_traci.TraCIException = Exception
            mock_traci.vehicle.getRoadID.return_value = "e0"
            mock_traci.vehicle.getLaneIndex.return_value = 0
            mock_traci.vehicle.getLanePosition.return_value = 160.0  # 40m remaining on e0
            mock_traci.vehicle.getRouteIndex.return_value = 0
            mock_traci.edge.getLaneNumber.return_value = 2
            mock_traci.lane.getLength.side_effect = lambda lid: lengths[lid]
            mock_traci.lane.getLinks.side_effect = lambda lid: links[lid]

        env_a2 = self._make_stub_env(agenda2=True)
        with patch("utils.mcw_train.traci") as mock_traci:
            setup_mock(mock_traci)
            self.assertAlmostEqual(env_a2._lane_connectivity(0), 1.0)
            self.assertAlmostEqual(env_a2._lane_connectivity(1), (40.0 + 67.0) / 120.0, places=5)

        env_a1 = self._make_stub_env(agenda2=False)
        with patch("utils.mcw_train.traci") as mock_traci:
            setup_mock(mock_traci)
            self.assertAlmostEqual(env_a1._lane_connectivity(1), 1.0)


if __name__ == "__main__":
    unittest.main()

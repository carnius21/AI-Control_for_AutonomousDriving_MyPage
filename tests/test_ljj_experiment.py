import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from utils.ljj_experiment import ExperimentEnv, SCENARIO, digest, environment, risk, traci


class LJJTests(unittest.TestCase):
    def test_risk_uses_closing_speed_and_preserves_overlap(self):
        v = traci.vehicle
        with patch.object(v, 'getIDList', return_value=['ego', 'front']), patch.object(v, 'getLeader', return_value=('front', 25.)), patch.object(v, 'getSpeed', side_effect=lambda x: 20. if x=='ego' else 10.):
            value = risk()
            self.assertEqual(value['ttc'], 2.5)
            self.assertEqual(value['required_decel'], 2.)
        with patch.object(v, 'getIDList', return_value=['ego', 'front']), patch.object(v, 'getLeader', return_value=('front', -1.)), patch.object(v, 'getSpeed', return_value=10.):
            value = risk()
            self.assertTrue(value['overlap'])
            self.assertIsNone(value['ttc'])

    def test_overlap_correction_does_not_change_reward_neighbor_query(self):
        env = ExperimentEnv.__new__(ExperimentEnv)
        env.mode, env.ego_id, env.visibility = 'observation', 'ego', 50.
        with patch.object(traci.vehicle, 'getNeighbors', return_value=[('side', -2.)]), patch.object(traci.vehicle, 'getSpeed', return_value=10.):
            env._building_obs = True
            self.assertEqual(env._neighbor(1, True), (0., 10.))
            env._building_obs = False
            self.assertIsNone(env._neighbor(1, True))

    def test_modes_preserve_frozen_traffic_and_separate_treatments(self):
        names = ['network.net.xml', 'highway.rou.xml', 'run.sumocfg']
        before = {n:digest(SCENARIO/n) for n in names}
        for mode in ['baseline', 'observation', 'action', 'reward']:
            env = environment(mode, 0)
            self.assertEqual(env.observation_space.shape, (47,))
            self.assertEqual(env.action_space.shape, (2,))
            self.assertEqual(len(env.routes), 16)
            self.assertEqual(env.lc_safety_enabled, mode=='action')
            self.assertEqual(env.rw.get('time_gap_s'), 1.5 if mode=='reward' else None)
            self.assertEqual(env.warmup_steps, 4500)
            self.assertEqual(env.navigation.horizon, 300.)
            env.close()
        self.assertEqual(before, {n:digest(SCENARIO/n) for n in names})


if __name__ == '__main__':
    unittest.main()

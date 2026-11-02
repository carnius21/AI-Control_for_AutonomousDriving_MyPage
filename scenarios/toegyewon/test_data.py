"""Boundary/corruption tests independent of installed SUMO execution."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from .behavior import RouteHeuristic
from .data_io import ShardWriter, iter_transitions


class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.record = dict(episode=0, t=0, observation=[0.] * 43, action_raw=[.25, -1.],
                           action={'lane_change': -1}, reward=.1, terminated=False, truncated=False,
                           state={'time': 1.}, detected_vehicles=[],
                           next_observation=[.1] * 43, next_state={'time': 1.2})

    def write(self, records):
        p = self.root / 'records.jsonl.gz'
        with gzip.open(p, 'wt', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r) + '\n')
        return p

    def compact(self):
        r = copy.deepcopy(self.record)
        del r['next_observation'], r['next_state']
        return r

    def test_consecutive_reconstruction(self):
        nxt = dict(self.record, t=1, observation=[.1] * 43, state={'time': 1.2}, terminated=True)
        records = list(iter_transitions(self.write([self.compact(), nxt])))
        self.assertEqual(records[0]['next_state'], nxt['state'])

    def test_no_cross_episode_or_gap(self):
        for changes in ({'episode': 1}, {'t': 2}):
            with self.assertRaises(ValueError):
                list(iter_transitions(self.write([self.compact(), dict(self.record, **changes)])))

    def test_terminal_and_final_next_required(self):
        for record in (self.compact(), dict(self.compact(), terminated=True)):
            with self.assertRaises(ValueError):
                list(iter_transitions(self.write([record])))
        with self.assertRaises(ValueError):
            list(iter_transitions(self.write([dict(self.compact(), terminated=True), dict(self.record, t=1)])))

    def test_partial_next_pair(self):
        record = self.compact()
        record['next_state'] = {}
        with self.assertRaises(ValueError):
            list(iter_transitions(self.write([record, dict(self.record, t=1)])))

    def test_corrupt_gzip(self):
        path = self.write([self.record])
        path.write_bytes(path.read_bytes()[:-6])
        with self.assertRaises((EOFError, OSError)):
            list(iter_transitions(path))

    def test_bounded_shards_and_pickle_free(self):
        writer = ShardWriter(self.root, 2)
        for t in range(5):
            writer.add(dict(self.record, t=t))
            self.assertLess(len(writer.records), 2)
        writer.flush()
        self.assertEqual(writer.count, 5)
        self.assertEqual(len(list(self.root.glob('shard_*.json'))), 3)
        with np.load(self.root / 'shard_00000.npz', allow_pickle=False) as z:
            self.assertEqual(z['detected_xy'].shape, (0, 2))
            np.testing.assert_array_equal(z['detected_offsets'], [0, 0, 0])
        self.assertEqual(len(list(iter_transitions(self.root / 'shard_00002.jsonl.gz'))), 1)

    def test_heuristic_observation_only_deterministic(self):
        obs = np.zeros(43, dtype=np.float32)
        obs[40], obs[9] = .5, 1
        policy = RouteHeuristic()
        np.testing.assert_array_equal(policy.predict(obs), policy.predict(obs))
        self.assertTrue((abs(policy.predict(obs)) <= 1).all())
        with self.assertRaises(ValueError):
            policy.predict(np.zeros(19))


if __name__ == '__main__':
    unittest.main()

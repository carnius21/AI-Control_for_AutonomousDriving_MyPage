"""Strict JSONL/NPZ and temporal integrity checks, one shard at a time."""
import json
from pathlib import Path
import numpy as np
from .data_io import arrays, iter_transitions, save_json, sha256


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_episode(attempt, metadata):
    attempt = Path(attempt)
    summary = json.loads((attempt / 'episode.json').read_text(encoding='utf-8'))
    previous, count, reward_sum = None, 0, 0.
    types, bus_detections, weave_bus = set(), 0, 0
    rejected, submitted, physical = 0, 0, 0
    dt, dim = metadata['config']['step_length'], metadata['observation_dimension']
    markers = sorted(attempt.glob('shard_*.json'))
    require(bool(markers), 'No committed shards')
    for index, marker in enumerate(markers):
        require(marker.stem == f'shard_{index:05d}', 'Missing shard')
        commit = json.loads(marker.read_text(encoding='utf-8'))
        expected_files = {marker.stem + '.jsonl.gz', marker.stem + '.npz'}
        require(set(commit['files']) == expected_files, 'Invalid shard filenames')
        for name, digest in commit['files'].items():
            require(sha256(attempt / name) == digest, 'Checksum mismatch: ' + name)
        records = list(iter_transitions(attempt / (marker.stem + '.jsonl.gz')))
        require(len(records) == commit['count'] and len(records) > 0, 'Shard count mismatch')
        with np.load(attempt / (marker.stem + '.npz'), allow_pickle=False) as z:
            expected = arrays(records)
            require(set(z.files) == set(expected), 'NPZ keys mismatch')
            for k, value in expected.items():
                require(z[k].dtype == value.dtype and np.array_equal(z[k], value), 'NPZ mismatch: ' + k)
        for r in records:
            for key in ('episode', 't', 'observation', 'action_raw', 'action', 'reward', 'terminated',
                        'truncated', 'state', 'detected_vehicles', 'event', 'next_observation', 'next_state'):
                require(key in r, 'Missing field: ' + key)
            require(r['run_id'] == metadata['run_id'], 'Run identity mismatch')
            require(type(r['episode']) is int and type(r['t']) is int, 'Invalid episode/time types')
            require(r['episode'] == summary['episode'] and r['t'] == count, 'Episode/t discontinuity')
            for key in ('observation', 'next_observation'):
                o = np.asarray(r[key])
                require(o.shape == (dim,) and np.isfinite(o).all() and (abs(o) <= 1.000001).all(), 'Invalid ' + key)
            raw = np.asarray(r['action_raw'])
            require(raw.shape == (2,) and np.isfinite(raw).all() and (abs(raw) <= 1).all(), 'Invalid action')
            a, ev, s, n = r['action'], r['event'], r['state'], r['next_state']
            require(a['accel_raw'] == raw[0] and a['lane_change_raw'] == raw[1], 'Raw action mismatch')
            direction = 1 if raw[1] >= .5 else -1 if raw[1] <= -.5 else 0
            require(type(a['lane_change']) is int and a['lane_change'] == direction, 'Lane action mismatch')
            require(type(a['lane_change_applied']) is bool, 'Invalid applied flag')
            require(not a['lane_change_applied'] or (direction != 0 and not a['rejection']), 'Invalid submission')
            require(type(r['reward']) in (float, int) and np.isfinite(r['reward']), 'Invalid reward')
            require(all(type(r[k]) is bool for k in ('terminated', 'truncated')), 'Invalid done flags')
            require(not (r['terminated'] and r['truncated']), 'Both done flags set')
            require(all(type(ev[k]) is bool for k in ('arrived', 'collided', 'lane_changed')), 'Invalid event flags')
            require(abs(n['time'] - s['time'] - dt) < 1e-7, 'State timestep mismatch')
            require(s['ego_alive'] and s['ego'] is not None, 'Missing current ego')
            require(ev['lane_before'] == s['ego']['lane_index'], 'Lane before mismatch')
            require(ev['lane_after'] == (n['ego']['lane_index'] if n['ego'] else 'absent'), 'Lane after mismatch')
            changed = bool(n['ego'] and s['ego']['edge'] == n['ego']['edge'] and s['ego']['lane'] != n['ego']['lane'])
            require(ev['lane_changed'] == changed, 'Physical lane-change mismatch')
            require(ev['status'] == n['status'], 'Status mismatch')
            require(r['truncated'] == (ev['status'] == 'timeout'), 'Timeout flag mismatch')
            require(ev['arrived'] == (ev['status'] == 'arrived'), 'Arrival flag mismatch')
            require((r['terminated'] or r['truncated']) == (ev['status'] != 'running'), 'Termination mismatch')
            if ev['collided']:
                require(r['terminated'] and ev['status'] == 'collision', 'Collision mismatch')
            if r['terminated'] or r['truncated']:
                require(r['reward'] == (2. if ev['arrived'] else -5.), 'Terminal reward mismatch')
            elif n['ego'] and 'allowed_speed' in n['ego']:
                expected_reward = .1 * n['ego']['speed'] / max(.1, n['ego']['allowed_speed'])
                expected_reward -= .1 if r['next_observation'][9] * metadata['config']['av'].get('visibility', 50) < 6 - 1e-6 else 0
                expected_reward -= .02 if a['rejection'] else 0
                require(abs(r['reward'] - expected_reward) < 1e-6, 'Running reward mismatch')
            if previous:
                require(not previous['terminated'] and not previous['truncated'], 'Record after episode end')
                require(previous['next_state'] == s and previous['next_observation'] == r['observation'], 'Temporal link mismatch')
            for world in (s, n):
                vehicles = {v['id']: v for v in world['vehicles']}
                require(len(vehicles) == len(world['vehicles']), 'Duplicate world vehicles')
                require(world['ego'] == vehicles.get(world['ego_id']), 'Stale/missing ego state')
                require(world['ego_alive'] == (world['ego'] is not None), 'Ego presence mismatch')
                types.update(v['type'] for v in vehicles.values())
            if n['ego'] is None:
                require(not any(r['next_observation']), 'Absent ego requires zero terminal observation')
            world = {v['id']: v for v in s['vehicles']}
            require(len({v['id'] for v in r['detected_vehicles']}) == len(r['detected_vehicles']), 'Duplicate detection')
            for v in r['detected_vehicles']:
                require(v['id'] in world, 'Detected vehicle absent from current world')
                actual = world[v['id']]
                for key in ('type', 'x', 'y', 'speed', 'length'):
                    require(v[key] == actual[key], 'Detection frame mismatch: ' + key)
                require(abs(v['relative_speed'] - actual['relative_speed']) < 1e-7, 'Relative speed mismatch')
                bus_detections += v['type'] == 'BUS'
                weave_bus += v['type'] == 'BUS' and s['ego']['edge'] == 'weave'
            rejected += bool(a['rejection'])
            submitted += a['lane_change_applied']
            physical += ev['lane_changed']
            reward_sum += r['reward']
            previous, count = r, count + 1
    require(previous['terminated'] or previous['truncated'], 'Incomplete episode; not training-ready')
    require(count == summary['transitions'], 'Episode count mismatch')
    require(abs(reward_sum - summary['return']) < 1e-8, 'Episode return mismatch')
    require(previous['event']['status'] == summary['status'], 'Episode outcome mismatch')
    return {'episode': summary['episode'], 'transitions': count, 'status': summary['status'],
            'return': reward_sum, 'vehicle_types': sorted(types), 'bus_detection_records': int(bus_detections),
            'weave_bus_detection_records': int(weave_bus), 'lane_requests_submitted': submitted,
            'lane_requests_rejected': rejected, 'physical_lane_changes': physical, 'shards': len(markers)}


def validate_dataset(directory):
    out = Path(directory)
    meta = json.loads((out / 'metadata.json').read_text(encoding='utf-8'))
    results = []
    for ep in range(meta['settings']['episodes']):
        parent = out / 'episodes' / f'{ep:06d}'
        summary = json.loads((parent / 'complete.json').read_text(encoding='utf-8'))
        require(summary['episode'] == ep and summary['seed'] == meta['settings']['seed'] + ep, 'Episode seed/id mismatch')
        require(Path(summary['attempt']).name == summary['attempt'], 'Invalid attempt name')
        attempt = parent / summary['attempt']
        require(json.loads((attempt / 'episode.json').read_text(encoding='utf-8')) == summary, 'Completion marker mismatch')
        results.append(validate_episode(attempt, meta))
    result = {'valid': True, 'run_id': meta['run_id'], 'episodes': results,
              'transitions': sum(r['transitions'] for r in results)}
    save_json(out / 'validation.json', result)
    return result


def compare_datasets(left, right):
    """Exact decoded transition equality, excluding only per-run identity."""
    from itertools import zip_longest
    for directory in (left, right):
        validate_dataset(directory)
    def transitions(directory):
        directory = Path(directory)
        for marker in sorted((directory / 'episodes').glob('*/complete.json')):
            info = json.loads(marker.read_text(encoding='utf-8'))
            for path in sorted((marker.parent / info['attempt']).glob('shard_*.jsonl.gz')):
                for record in iter_transitions(path):
                    record.pop('run_id')
                    yield record
    count = 0
    for a, b in zip_longest(transitions(left), transitions(right)):
        require(a == b, f'Reproduction mismatch at transition {count}')
        count += 1
    return {'identical_decoded_transitions': True, 'transitions': count,
            'left': str(left), 'right': str(right)}

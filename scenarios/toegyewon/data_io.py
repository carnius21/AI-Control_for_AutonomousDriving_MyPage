"""Bounded shards using the course collector's JSONL and flat detection layout.

Full next states are retained by this writer. The reader also supports compact
course records, but only reconstructs within consecutive episode timesteps.
"""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def iter_transitions(path):
    previous = None
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            current = json.loads(line)
            if previous is not None:
                missing = [k not in previous for k in ('next_observation', 'next_state')]
                if any(missing):
                    if not all(missing) or previous['terminated'] or previous['truncated']:
                        raise ValueError('Incomplete terminal/next pair')
                    if current['episode'] != previous['episode'] or current['t'] != previous['t'] + 1:
                        raise ValueError('Cannot reconstruct across episode/time boundary')
                    previous['next_observation'] = current['observation']
                    previous['next_state'] = current['state']
                yield previous
            previous = current
    if previous is not None:
        if 'next_observation' not in previous or 'next_state' not in previous:
            raise ValueError('Final record has no explicit next state')
        yield previous


def arrays(records):
    types = {'observation': np.float32, 'action_raw': np.float32,
             'reward': np.float64, 'next_observation': np.float32,
             'terminated': np.bool_, 'truncated': np.bool_, 'episode': np.int64, 't': np.int64}
    result = {k: np.asarray([r[k] for r in records], dtype=d) for k, d in types.items()}
    result['lane_change'] = np.asarray([r['action']['lane_change'] for r in records], dtype=np.int8)
    positions, offsets = [], [0]
    for r in records:
        positions.extend([[v['x'], v['y']] for v in r['detected_vehicles']])
        offsets.append(len(positions))
    result['detected_xy'] = np.asarray(positions, dtype=np.float32).reshape(-1, 2)
    result['detected_offsets'] = np.asarray(offsets, dtype=np.int64)
    return result


class ShardWriter:
    def __init__(self, directory, size=256):
        if size < 1:
            raise ValueError('shard size must be positive')
        self.directory, self.size = Path(directory), size
        self.directory.mkdir(parents=True, exist_ok=True)
        self.records, self.index, self.count = [], 0, 0

    def add(self, record):
        self.records.append(record)
        if len(self.records) >= self.size:
            self.flush()

    def flush(self):
        if not self.records:
            return
        stem = self.directory / f'shard_{self.index:05d}'
        jp, np = Path(str(stem) + '.jsonl.gz'), Path(str(stem) + '.npz')
        if jp.exists() or np.exists():
            raise FileExistsError(stem)
        partial = Path(str(jp) + '.partial')
        with gzip.open(partial, 'wt', encoding='utf-8') as f:
            for r in self.records:
                f.write(json.dumps(r, separators=(',', ':'), allow_nan=False) + '\n')
        partial.replace(jp)
        partial = Path(str(np) + '.partial')
        with partial.open('wb') as f:
            __import__('numpy').savez_compressed(f, **arrays(self.records))
        partial.replace(np)
        save_json(str(stem) + '.json', {'count': len(self.records),
                  'files': {p.name: sha256(p) for p in (jp, np)}})
        self.count += len(self.records)
        self.records.clear()
        self.index += 1

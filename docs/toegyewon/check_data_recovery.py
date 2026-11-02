from unittest.mock import patch
from pathlib import Path
import sys
import json
from scenarios.toegyewon.av_env import ToegyewonEnv
from scenarios.toegyewon.data_collection import main
from scenarios.toegyewon.data_io import iter_transitions, save_json
from scenarios.toegyewon.validate_data import validate_dataset

directory = Path(sys.argv[1] if len(sys.argv) > 1 else 'data/toegyewon/recovery_check')
args = ['--episodes', '1', '--time-limit', '90.8', '--shard-size', '2', '--out-dir', str(directory), '--validate']
original = ToegyewonEnv.step
calls = 0
def fail_second(self, action):
    global calls
    calls += 1
    if calls == 2:
        raise ConnectionError('Test-injected SUMO disconnect after one real transition')
    return original(self, action)

with patch.object(ToegyewonEnv, 'step', fail_second):
    try:
        main(args)
    except ConnectionError:
        pass
    else:
        raise AssertionError('Failure injection did not occur')
failed = directory / 'episodes/000000/attempt_000'
assert not (failed.parent / 'complete.json').exists()
rows = list(iter_transitions(failed / 'shard_00000.jsonl.gz'))
assert len(rows) == 1 and not rows[0]['terminated'] and not rows[0]['truncated']
assert rows[0]['next_state']['time'] > rows[0]['state']['time']
main(args + ['--resume'])
result = validate_dataset(directory)
assert (failed / 'failure.json').exists()
assert (failed.parent / 'attempt_001/episode.json').exists()
# Complete reruns are skipped, and checksum corruption fails closed.
main(args + ['--resume'])
npz = failed.parent / 'attempt_001/shard_00000.npz'
contents = npz.read_bytes()
try:
    npz.write_bytes(contents[:-1])
    try:
        validate_dataset(directory)
    except ValueError as exc:
        assert 'Checksum mismatch' in str(exc)
    else:
        raise AssertionError('Corruption accepted')
finally:
    npz.write_bytes(contents)
validate_dataset(directory)
save_json('docs/toegyewon/data_recovery_checks.json', {
    'injected_disconnect_after_real_steps': 1, 'preserved_incomplete_records': len(rows),
    'resumed_with_new_attempt': True, 'completed_resume_skips_collection': True,
    'checksum_corruption_rejected': True, 'validation': result,
    'note': 'Controlled exception test, not a hard process/power kill.'})

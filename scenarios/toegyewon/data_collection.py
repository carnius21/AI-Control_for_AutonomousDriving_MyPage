"""Actual external-policy transitions; no training or invented SUMO actions."""
import argparse
import datetime
import json
import platform
import shutil
import subprocess
import uuid
from pathlib import Path
import numpy as np
from .av_env import ToegyewonEnv
from .av_observation import SCHEMAS
from .behavior import RouteHeuristic
from .data_io import ShardWriter, save_json, sha256
from .network import build, binary
from .policy import load_ppo

ROOT = Path(__file__).resolve().parents[2]


def provenance():
    paths = sorted((ROOT / 'scenarios/toegyewon').glob('*.py'))
    paths += [ROOT / 'collect_toegyewon_data.py', ROOT / 'collect_pomdp_data.py']
    paths += sorted((ROOT / 'scenarios/toegyewon/source').rglob('*'))
    return {'files': {str(p.relative_to(ROOT)): sha256(p) for p in paths if p.is_file()},
            'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
            'python': platform.python_version(), 'numpy': np.__version__,
            'sumo': subprocess.check_output([binary('sumo'), '--version'], text=True).splitlines()[0]}


def collect_episode(out, manifest, episode, args, run_id):
    parent = out / 'episodes' / f'{episode:06d}'
    parent.mkdir(parents=True, exist_ok=True)
    attempts = list(parent.glob('attempt_*'))
    attempt = parent / f'attempt_{len(attempts):03d}'
    attempt.mkdir()  # Never overwrite an interrupted attempt.
    sim = attempt / 'sumo'
    sim.mkdir()
    shutil.copyfile(out / 'build/toegyewon.net.xml', sim / 'toegyewon.net.xml')
    env = ToegyewonEnv(sim, manifest, 'external', collect_state=True, record_trace=False)
    cfg = manifest['config']['av']
    policy = (load_ppo(args.checkpoint, env.obs_dim, env.schema, args.policy_activation)
              if args.policy == 'ppo' else RouteHeuristic(args.observation, env.visibility,
                                                         cfg.get('speed_normalization', 33.33)))
    writer = ShardWriter(attempt, args.shard_size)
    total, t = 0., 0
    try:
        obs, _ = env.reset(seed=args.seed + episode)
        state = env.get_privileged_state()
        while not env.done:
            detected = env.get_detected_vehicles()
            raw = np.asarray(policy.predict(obs.copy(), deterministic=True), dtype=np.float32)
            if raw.shape != (2,) or not np.isfinite(raw).all() or (abs(raw) > 1).any():
                raise ValueError('Policy must output two finite actions in [-1,1]')
            nxt, reward, terminated, truncated, info = env.step(raw)
            next_state = env.get_privileged_state()
            a = info['action']
            record = {'run_id': run_id, 'episode': episode, 't': t,
                'observation': obs.tolist(), 'action_raw': raw.tolist(),
                'action': {'accel_raw': float(raw[0]), 'lane_change_raw': float(raw[1]),
                    'lane_change': a['lane_direction'], 'lane_change_applied': a['lane_request_submitted'],
                    'rejection': a['rejection'], 'requested_accel': a['requested_accel'],
                    'requested_speed': a['requested_speed']},
                'reward': reward, 'terminated': bool(terminated), 'truncated': bool(truncated),
                'state': state, 'detected_vehicles': detected,
                'event': {'collided': info['collided'], 'arrived': info['arrived'],
                    'lane_before': info['lane_before'],
                    'lane_after': info['lane_after'] if info['lane_after'] is not None else 'absent',
                    'lane_changed': info['lane_change_applied'], 'lane_delta': info['lane_change'],
                    'status': info['status'], 'teleported': env.ego_id in env.teleports,
                    'actual_acceleration': next_state['ego']['acceleration'] if next_state['ego'] else None},
                'next_observation': nxt.tolist(), 'next_state': next_state}
            writer.add(record)
            total += reward
            t += 1
            obs, state = nxt, next_state
        writer.flush()
        result = env.finish(drain=False)
        summary = {'episode': episode, 'seed': args.seed + episode, 'attempt': attempt.name,
            'transitions': writer.count, 'return': total, 'status': result['status'],
            'route': cfg['route'], 'collided': env.ego_id in result['collisions'],
            'weave_bus_neighbor_seconds': result['av_weave_bus_neighbor_seconds'],
            'weave_car_neighbor_seconds': result['av_weave_car_neighbor_seconds'],
            'lane_changes': len(result['av_lane_changes']), 'min_acceleration': result['av_min_acceleration']}
        save_json(attempt / 'episode.json', summary)
        save_json(parent / 'complete.json', summary)
        return summary
    except BaseException as exc:
        writer.flush()  # All buffered records already have real next states.
        save_json(attempt / 'failure.json', {'type': type(exc).__name__, 'message': str(exc),
                  'saved_transitions': writer.count, 'episode': episode, 'seed': args.seed + episode})
        raise
    finally:
        env.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--episodes', type=int, default=2)
    p.add_argument('--policy', choices=['heuristic', 'ppo'], default='heuristic')
    p.add_argument('--checkpoint')
    p.add_argument('--policy-activation', choices=['relu', 'tanh', 'elu'], default='relu')
    p.add_argument('--av-route', choices=['pink', 'green'], default='pink')
    p.add_argument('--av-depart', type=float, default=90)
    p.add_argument('--traffic', choices=['low', 'medium', 'high'], default='medium')
    p.add_argument('--weave-factor', type=float)
    p.add_argument('--bus-ratio', type=float, default=.1)
    p.add_argument('--seed', type=int, default=21)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--config', type=Path)
    p.add_argument('--observation', choices=['route', 'legacy'], default='route')
    p.add_argument('--time-limit', type=float, default=600)
    p.add_argument('--shard-size', type=int, default=256)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--validate', action='store_true')
    p.add_argument('--validate-only', action='store_true')
    p.add_argument('--compare-with', type=Path, help='Validate and compare decoded transitions with another run')
    args = p.parse_args(argv)
    from .validate_data import validate_dataset
    out = args.out_dir.resolve()
    if args.validate_only:
        print(json.dumps(validate_dataset(out), indent=2))
        if args.compare_with:
            from .validate_data import compare_datasets
            print(json.dumps(compare_datasets(out, args.compare_with), indent=2))
        return
    if args.compare_with:
        p.error('--compare-with requires --validate-only')
    if args.episodes < 1 or args.shard_size < 1 or not 0 <= args.seed < 2**31 - args.episodes:
        p.error('positive episodes/shard-size and nonnegative 31-bit episode seeds required')
    if args.policy == 'ppo' and not args.checkpoint:
        p.error('--policy ppo requires a compatible trained --checkpoint')
    settings = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()
                if k not in ('out_dir', 'resume', 'validate', 'validate_only', 'compare_with')}
    settings['config_sha256'] = sha256(args.config or ROOT / 'scenarios/toegyewon/config.json')
    settings['checkpoint_sha256'] = sha256(args.checkpoint) if args.checkpoint else None
    prov = provenance()
    if args.resume:
        meta = json.loads((out / 'metadata.json').read_text(encoding='utf-8'))
        if settings != meta['settings'] or prov['files'] != meta['provenance']['files'] or prov['sumo'] != meta['provenance']['sumo']:
            raise ValueError('Resume requires identical settings, code, sources and SUMO version')
        manifest = json.loads((out / 'build/manifest.json').read_text(encoding='utf-8'))
        if sha256(out / 'build/toegyewon.net.xml') != meta['network_sha256']:
            raise ValueError('Network checksum mismatch')
        if sha256(out / 'build/manifest.json') != meta['manifest_sha256']:
            raise ValueError('Manifest checksum mismatch')
    else:
        if out.exists() and any(out.iterdir()):
            raise FileExistsError('Use a new output directory or --resume')
        out.mkdir(parents=True, exist_ok=True)
        traffic = {'profile': args.traffic}
        if args.weave_factor is not None:
            traffic['weave_factor'] = args.weave_factor
        build(out / 'build', args.config, traffic, args.seed, args.bus_ratio,
              {'enabled': True, 'route': args.av_route, 'depart': args.av_depart,
               'observation': args.observation, 'time_limit': args.time_limit, 'controller': 'external'})
        manifest = json.loads((out / 'build/manifest.json').read_text(encoding='utf-8'))
        schema, dim = SCHEMAS[args.observation]
        meta = {'format_version': 1, 'run_id': uuid.uuid4().hex,
            'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'settings': settings, 'provenance': prov, 'config': manifest['config'],
            'demand': manifest['demand'], 'observation_dimension': dim, 'observation_schema': schema,
            'action_dimension': 2, 'policy_version': RouteHeuristic.version if args.policy == 'heuristic' else 'checkpoint',
            'controller': 'external with SUMO safety, strategic/cooperative lane changes',
            'action_definition': '[normalized acceleration, lane direction threshold +/-0.5]; applied means submitted',
            'coordinates': {'units': 'm', 'frame': 'projected WGS84 minus projected origin; SUMO local XY',
                            'projection': manifest['config']['projection'],
                            'origin_lon_lat': manifest['config']['origin_lon_lat']},
            'course_observation_note': 'Evaluation says 19; current course code 31; this run uses actual policy input without padding/truncation.',
            'network_sha256': sha256(out / 'build/toegyewon.net.xml'),
            'manifest_sha256': sha256(out / 'build/manifest.json')}
        from pyproj import Transformer
        meta['coordinates']['projected_origin_xy'] = list(Transformer.from_crs(
            'EPSG:4326', manifest['config']['projection'], always_xy=True).transform(
                *manifest['config']['origin_lon_lat']))
        meta['observation_indices'] = {
            '0': 'ego speed / speed_normalization',
            '1:21': 'offsets [+2,+1,0,-1,-2], each front gap/relative speed/rear gap/relative speed',
            '21:26': 'lane connectivity; nonexistent=-1', '26:31': 'normalized local density',
            'normalization': 'gaps / visibility, relative speeds / speed_normalization; clip [-1,1]'}
        if dim == 43:
            meta['observation_indices'].update({'31:36': 'route next-edge reachability',
                '36': 'remaining lane distance / visibility', '37': 'best lane offset / 4',
                '38': 'lane index / max(1,lane count-1)', '39': 'route index / max(1,route length-1)',
                '40': 'allowed speed / speed_normalization', '41': 'internal junction flag',
                '42': 'best lane remaining distance / visibility'})
        save_json(out / 'metadata.json', meta)
    summaries = []
    for ep in range(args.episodes):
        completed = out / 'episodes' / f'{ep:06d}' / 'complete.json'
        if completed.exists():
            from .validate_data import validate_episode
            summary = json.loads(completed.read_text(encoding='utf-8'))
            validate_episode(completed.parent / summary['attempt'], meta)
        else:
            summary = collect_episode(out, manifest, ep, args, meta['run_id'])
        summaries.append(summary)
        save_json(out / 'summary.json', {'episodes': summaries, 'transitions': sum(s['transitions'] for s in summaries),
            'success_rate': sum(s['status'] == 'arrived' for s in summaries) / len(summaries),
            'collision_rate': sum(s['collided'] for s in summaries) / len(summaries),
            'mean_return': sum(s['return'] for s in summaries) / len(summaries)})
        print(json.dumps(summary), flush=True)
    if args.validate:
        print(json.dumps(validate_dataset(out), indent=2))

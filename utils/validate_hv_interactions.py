"""Measure mixed-HV traffic; this is not learned-AV performance evaluation.

Run from the project folder: python -m utils.validate_hv_interactions
Raw logs, vehicle trajectories, lane changes and the report remain in --output.
"""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get('SUMO_HOME'):
    for candidate in (r'C:\Program Files (x86)\Eclipse\Sumo',
                      r'C:\Program Files\Eclipse\Sumo', '/usr/share/sumo',
                      '/opt/homebrew/opt/sumo/share/sumo'):
        if Path(candidate).is_dir():
            os.environ['SUMO_HOME'] = candidate
            break
if os.environ.get('SUMO_HOME'):
    sys.path.append(str(Path(os.environ['SUMO_HOME']) / 'tools'))
from sumolib import checkBinary
from env.road_config import ROAD, EGO, TRAFFIC
from env.mdp_config import SIMULATION, ACTION
from env.road_builder import build


def analyse(directory, seed):
    stats = ET.parse(directory / 'statistics.xml').getroot()
    trips = ET.parse(directory / 'trips.xml').getroot().findall('tripinfo')
    hv = {t.get('id'): t.get('vType') for t in trips if t.get('vType').startswith(('car_', 'bus_'))}
    changes = [e.attrib for e in ET.parse(directory / 'lanechanges.xml').getroot()
               if e.tag == 'change' and e.get('id') in hv]
    near = [c for c in changes if any(c.get(k, 'None') != 'None'
            and float(c[k]) <= 30 for k in ('leaderGap', 'followerGap'))]
    followed, braked, sustained, pairs = set(), set(), set(), set()
    streak, last_time = {}, {}
    sample_count = following_samples = braking_samples = 0
    by_edge = Counter()
    by_model = Counter()
    by_pair = Counter()
    # 1-second samples, longitudinal network leader (not XY proximity).
    for event, elem in ET.iterparse(directory / 'fcd.xml', events=('end',)):
        if elem.tag != 'timestep':
            continue
        time = float(elem.get('time'))
        for v in elem:
            vid = v.get('id')
            if vid not in hv:
                continue
            speed = float(v.get('speed'))
            if speed < 2.0:
                continue
            sample_count += 1
            lid = v.get('leaderID', '')
            gap = float(v.get('leaderGap', '-1'))
            # Proxy for car-following exposure, not a collision or TTC metric.
            if lid in hv and 0 <= gap / speed <= 2.0:
                following_samples += 1
                followed.add(vid)
                key = (vid, lid)
                pairs.add(key)
                streak[key] = streak.get(key, 0) + 1 if abs(time-last_time.get(key, -100)-1) < .01 else 1
                last_time[key] = time
                if streak[key] >= 4:  # four samples span at least three seconds
                    sustained.add(vid)
                edge = v.get('lane').rsplit('_', 1)[0]
                by_edge[edge] += 1
                by_model[hv[vid]] += 1
                by_pair[hv[vid] + ' -> ' + hv[lid]] += 1
                if float(v.get('acceleration', '0')) <= -.5:
                    braking_samples += 1
                    braked.add(vid)
        elem.clear()
    safety = stats.find('safety').attrib
    teleports = stats.find('teleports').attrib
    vehicles = stats.find('vehicles').attrib
    waiting = [float(t.get('waitingTime')) for t in trips]
    result = dict(seed=seed, vehicles=vehicles, safety=safety, teleports=teleports,
        type_counts=dict(Counter(hv.values())), hv_count=len(hv), total_arrivals=len(trips),
        mean_wait_seconds=round(sum(waiting)/max(len(waiting), 1), 3),
        max_wait_seconds=max(waiting, default=0),
        lane_changes=dict(total=len(changes), vehicles=len({c['id'] for c in changes}),
            reasons=dict(Counter(c['reason'] for c in changes)),
            by_model=dict(Counter(c['type'] for c in changes)),
            by_from_edge=dict(Counter(c['from'].rsplit('_', 1)[0] for c in changes)),
            target_neighbor_within_30m=len(near)),
        following=dict(vehicles=len(followed), sustained_3s_vehicles=len(sustained),
            unique_directed_pairs=len(pairs), samples=following_samples,
            eligible_moving_samples=sample_count,
            share_of_moving_samples=round(following_samples/max(sample_count, 1), 4),
            braking_vehicles=len(braked), braking_samples=braking_samples,
            by_edge_samples=dict(by_edge), by_model_samples=dict(by_model),
            by_model_pair_samples=dict(by_pair)))
    result['network_check_passed'] = (vehicles['running'] == '0' and vehicles['waiting'] == '0'
        and int(vehicles['inserted']) == len(trips) and teleports['total'] == '0'
        and safety['collisions'] == '0' and safety['emergencyStops'] == '0'
        and {'car_krauss','car_idm','car_eidm','car_acc'} <= set(result['type_counts']))
    # Hard braking is an observed interaction outcome, not automatically a broken network.
    # Preserve its count and log for comfort/safety review instead of suppressing it.
    result['hard_braking_review_required'] = int(safety['emergencyBraking']) > 0
    if 'west_to_local' in ROAD.get('routes', {}):
        # Measure actual SUMO lane changes and destinations, not just lane connections.
        exit_trips = [t for t in trips if t.get('id', '').startswith('flow_west_to_local.')]
        ramp_trips = [t for t in trips if t.get('id', '').startswith(
            ('flow_north_to_west.', 'flow_south_to_west.'))]
        exit_ids = {t.get('id') for t in exit_trips}
        ramp_ids = {t.get('id') for t in ramp_trips}
        weave = [c for c in changes if c['from'].startswith('west_accel_')]
        into_exit = {c['id'] for c in weave if c['id'] in exit_ids and c['to'] == 'west_accel_0'}
        into_main = {c['id'] for c in weave if c['id'] in ramp_ids
                     and c['from'] == 'west_accel_0' and c['to'] == 'west_accel_1'}
        result['west_auxiliary'] = dict(lane_change_events=len(weave),
            main_to_exit_arrivals=len(exit_ids), main_to_exit_changed_to_lane0=len(into_exit),
            ramp_to_main_arrivals=len(ramp_ids), ramp_to_main_changed_0_to_1=len(into_main),
            exit_arrival_lanes=dict(Counter(t.get('arrivalLane') for t in exit_trips)),
            max_exit_wait=max((float(t.get('waitingTime')) for t in exit_trips), default=0),
            observed_both_movements=bool(exit_ids and ramp_ids)
                and into_exit == exit_ids and into_main == ramp_ids
                and all(t.get('arrivalLane') == 'west_local_exit_0' for t in exit_trips))
    (directory / 'metrics.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('seed','type_counts','safety','teleports','network_check_passed')}), flush=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT/'results'/('hv_'+datetime.now().strftime('%Y%m%d_%H%M%S')))
    ap.add_argument('--seeds', type=int, nargs='+', default=[42,7,23])
    ap.add_argument('--end', type=float, default=1200)
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if len(set(args.seeds)) != len(args.seeds):
        ap.error('Seeds must be unique')
    if (out/'report.json').exists():
        ap.error('Report exists; choose a new --output folder to preserve evidence')
    cfg = build(ROAD, EGO, TRAFFIC, str(out/'network'))
    def run(seed):
        d = out/str(seed); d.mkdir(exist_ok=True)
        cmd = [checkBinary('sumo'), '-c', cfg, '--seed', str(seed), '--end', str(args.end),
            '--no-step-log', 'true', '--no-warnings', 'false',
            '--statistic-output', str(d/'statistics.xml'),
            '--tripinfo-output', str(d/'trips.xml'),
            '--collision-output', str(d/'collisions.xml'),
            '--lanechange-output', str(d/'lanechanges.xml'),
            '--fcd-output', str(d/'fcd.xml'), '--device.fcd.period', '1',
            '--fcd-output.acceleration', 'true', '--fcd-output.max-leader-distance', '80',
            '--fcd-output.attributes', 'id,type,speed,lane,acceleration,leaderID,leaderGap,leaderSpeed']
        if seed == 42 and args.end > 300:
            cmd += ['--save-state.times', '300', '--save-state.files', str(d/'state300.xml')]
        (d/'command.json').write_text(json.dumps(cmd, indent=2), encoding='utf-8')
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        (d/'sumo.log').write_text(p.stdout+p.stderr, encoding='utf-8')
        if p.returncode:
            raise RuntimeError(p.stderr)
        return analyse(d, seed)
    with ThreadPoolExecutor(max_workers=min(len(args.seeds), 3)) as pool:
        results = list(pool.map(run, args.seeds))
    report = dict(scope='HV interaction proxies; no trained AV evaluation',
        sumo_version=subprocess.check_output([checkBinary('sumo'), '--version'], text=True).splitlines()[0],
        end_seconds=args.end, step_seconds=SIMULATION['step_length'],
        configured_hv_probabilities={k:v['probability'] for k,v in TRAFFIC['controllers'].items()},
        demand_vehicles_per_hour=TRAFFIC['vehs_per_hour'], flow_end_seconds=TRAFFIC['flow_end'],
        av_rule_lane_change_gate=ACTION['lane_change_safety']['enabled'],
        definitions=dict(following='Network leader is another HV; speed >= 2 m/s; physical gap / own speed <= 2 s; sampled every 1 s.',
            sustained='The same HV follows the same HV for at least 4 consecutive samples (3 seconds).',
            braking='Following proxy above AND acceleration <= -0.5 m/s^2; descriptive co-occurrence, not a causal proof.',
            near_lane_change='Actual SUMO lane change with target-lane leader or follower within 30 m.',
            adequacy='No universal adequacy threshold; evaluate learned AV exposure on the same roads separately.'),
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
                       for f in ('env/road_config.py','env/mdp_config.py','env/road_builder.py','env/sumo_env.py')},
        results=results)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Report:', out/'report.json', flush=True)
    return 0 if all(r['network_check_passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

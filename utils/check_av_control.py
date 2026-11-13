"""Check AV command handling and HV exposure without training a policy.

Run: python -m utils.check_av_control
Uses localhost TraCI. The negative control deliberately sets up an unsafe action
in an isolated zero-flow network. Production traffic and geometry are untouched.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse
import copy
import hashlib
import json
import numpy as np
from env.sumo_env import SumoHighwayEnv, traci
from env.road_config import ROAD, EGO, TRAFFIC
from env.mdp_config import SIMULATION, OBSERVATION, ACTION, REWARD
from env.road_builder import build

ROOT = Path(__file__).resolve().parents[1]


def make_env(cfg, traffic, action=ACTION, sim=SIMULATION):
    return SumoHighwayEnv(cfg, ROAD, EGO, sim, OBSERVATION, action, REWARD,
                         traffic=traffic, gui=False)


def negative_control(out):
    traffic = copy.deepcopy(TRAFFIC)
    traffic.update(vehs_per_hour=0, demo_vehicle=False)
    cfg = build(ROAD, EGO, traffic, str(out/'isolated_negative_control'))
    results = []
    for gate in (True, False):
        action = copy.deepcopy(ACTION)
        action['lane_change_safety']['enabled'] = gate
        sim = {**SIMULATION, 'warmup_steps': 0}
        # The skeleton draws its SUMO seed from NumPy, independently of reset(seed).
        np.random.seed(42)
        env = make_env(cfg, traffic, action, sim)
        try:
            env.reset(seed=42)
            traci.vehicle.add('probe_hv', 'r0', typeID='car_idm', departLane='1',
                departPos=str(traci.vehicle.getLanePosition(env.ego_id)), departSpeed='10')
            traci.simulationStep()
            # Fixed-lane obstacle ONLY for this deliberate negative control.
            # In production HVs retain their normal autonomous lane-changing model.
            traci.vehicle.setLaneChangeMode('probe_hv', 512)
            before = {v:dict(lane=traci.vehicle.getLaneID(v),
                      pos=traci.vehicle.getLanePosition(v),speed=traci.vehicle.getSpeed(v))
                      for v in traci.vehicle.getIDList()}
            obs, reward, done, cut, info = env.step(np.array([0., 1.]))
            events = [dict(info=info, reward=reward, terminated=done, truncated=cut)]
            for _ in range(3):
                if done:
                    break
                obs, reward, done, cut, info = env.step(np.array([0., 0.]))
                events.append(dict(info=info,reward=reward,terminated=done,truncated=cut))
            results.append(dict(rule_gate_enabled=gate,before=before,events=events))
        finally:
            env.close()
    blocked = not results[0]['events'][0]['info']['lane_change_applied']
    applied = results[1]['events'][0]['info']['lane_change_applied']
    collided = any(e['info']['collided'] and e['terminated'] and e['reward'] < 0
                   for e in results[1]['events'])
    return dict(passed=bool(blocked and applied and collided), results=results,
        note='With collision.action=remove, SUMO may also emit arrived=True. The existing reward and evaluator prioritize collided, so this is a collision, not a completion.')


def exposure(cfg, seed, seconds):
    np.random.seed(seed)
    env = make_env(cfg, TRAFFIC)
    try:
        obs, _ = env.reset(seed=seed)
        initial = sum(traci.vehicle.getTypeID(v).startswith('car_') for v in traci.vehicle.getIDList())
        counts, locations, seen = Counter(), Counter(), set()
        steps, last = 0, {}
        for _ in range(round(seconds/SIMULATION['step_length'])):
            ego = env.ego_id
            locations[traci.vehicle.getRoadID(ego)] += 1
            neighbors = [traci.vehicle.getLeader(ego, 80),traci.vehicle.getFollower(ego, 80)]
            for mode in range(4):
                neighbors.extend(traci.vehicle.getNeighbors(ego, mode))
            near = {v for item in neighbors if item for v,g in [item] if v and 0 <= g <= 40
                    and traci.vehicle.getTypeID(v).startswith('car_')}
            if near:
                counts['hv_within_40m_steps'] += 1
                seen.update(near)
            if neighbors[0] and neighbors[0][0] in near:
                counts['leader_within_40m_steps'] += 1
            if neighbors[1] and neighbors[1][0] in near:
                counts['follower_within_40m_steps'] += 1
            obs, reward, done, cut, last = env.step(np.array([0., 0.]))
            steps += 1
            if obs.shape != (31,) or not np.isfinite(obs).all():
                raise RuntimeError('Invalid observation')
            if done or cut:
                break
        return dict(seed=seed,initial_hv=initial,steps=steps,
            seconds=steps*SIMULATION['step_length'],unique_nearby_hv=len(seen),
            exposure_steps=dict(counts),visited_edges=dict(locations),last_info=last)
    finally:
        env.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT/'results'/('av_control_'+datetime.now().strftime('%Y%m%d_%H%M%S')))
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():
        ap.error('Choose a new output folder to preserve the existing report')
    control = negative_control(out)
    print('Unsafe-command negative control:', control['passed'], flush=True)
    cfg = build(ROAD, EGO, TRAFFIC, str(out/'production_network'))
    exposures = []
    for seed in (42,7,23):
        r = exposure(cfg,seed,60)
        exposures.append(r)
        print(json.dumps(r), flush=True)
    report = dict(scope='Interface/negative-control/exposure checks; NOT trained-AV performance.',
        policy='Constant-speed lane-keeping action [0,0] for 60 seconds in exposure checks.',
        near_definition='Network leader/follower or adjacent neighbor within 0..40 m longitudinal gap.',
        rule_gate_enabled=ACTION['lane_change_safety']['enabled'],
        negative_control=control, exposure=exposures,
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
                       for f in ('env/road_config.py','env/mdp_config.py','env/sumo_env.py','utils/check_av_control.py')})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Report:',out/'report.json',flush=True)
    return 0 if control['passed'] and all(r['initial_hv']>0 and r['unique_nearby_hv']>0 for r in exposures) else 1


if __name__ == '__main__':
    raise SystemExit(main())

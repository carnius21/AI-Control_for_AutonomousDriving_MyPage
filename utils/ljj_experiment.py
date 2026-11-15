"""Local CPU experiments on the team's frozen entry-preparation scenario."""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

# Works with both the official Windows installation and the verified pip wheel.
if not os.environ.get('SUMO_HOME'):
    try:
        import sumo
        os.environ['SUMO_HOME'] = sumo.SUMO_HOME
    except ImportError:
        pass
import numpy as np
import torch
from env import ic_experiment as ic
from env.navigation_clarity import ClarityEnv
from env.navigation_observation import RouteNavigation
from env.sumo_env import traci
from train import HPARAMS, EGO, ROAD, TRAFFIC, SIMULATION, OBSERVATION, ACTION, REWARD
from algorithms.ppo import PPO
from utils.logger import RunLogger

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / 'scenarios/hv_high15000_entryprep'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def risk():
    v = traci.vehicle
    if 'ego' not in v.getIDList():
        return dict(leader_present=False, gap=None, closing_speed=None, ttc=None, required_decel=None, overlap=False)
    leader = v.getLeader('ego', 50.)
    if not leader or not leader[0] or leader[1] > 50:
        return dict(leader_present=False, gap=None, closing_speed=None, ttc=None, required_decel=None, overlap=False)
    gap = float(leader[1])  # TraCI gap excludes ego minGap; retain its definition.
    closing = max(0., v.getSpeed('ego') - v.getSpeed(leader[0]))
    return dict(leader_present=True, leader_id=leader[0], ego_speed=float(v.getSpeed('ego')), leader_speed=float(v.getSpeed(leader[0])), gap=gap, closing_speed=closing,
                ttc=max(gap, 0.) / closing if closing > 1e-6 else None,
                required_decel=closing ** 2 / (2 * max(gap, .1)), overlap=gap < 0)


class ExperimentEnv(ClarityEnv):
    def __init__(self, *args, mode='baseline', **kwargs):
        self.mode = mode
        super().__init__(*args, clarity='baseline', **kwargs)

    def _neighbor(self, offset, leader):
        # Observation-only: retain longitudinal overlap rather than dropping it.
        if self.mode == 'observation' and getattr(self, '_building_obs', False) and abs(offset) <= 1:
            if offset == 0:
                item = traci.vehicle.getLeader(self.ego_id, self.visibility) if leader else traci.vehicle.getFollower(self.ego_id, self.visibility)
                pairs = [item] if item and item[0] else []
            else:
                modes = self._NEIGHBOR_MODES[offset]
                pairs = traci.vehicle.getNeighbors(self.ego_id, modes[0 if leader else 1])
            pairs = [(vid, gap) for vid, gap in pairs if gap <= self.visibility]
            if pairs:
                vid, gap = min(pairs, key=lambda p: p[1])
                return max(0., float(gap)), float(traci.vehicle.getSpeed(vid))
        return super()._neighbor(offset, leader)

    def _get_obs(self):
        self._building_obs = True
        try:
            obs = super()._get_obs()
        finally:
            self._building_obs = False
        if self.mode == 'observation' and self.ego_id in traci.vehicle.getIDList():
            nav = self.navigation_context()
            r = risk()
            # Reuse baseline's ten zero padding coordinates: same model and initial weights.
            obs[37:44] = [1. if nav['current_targets'] else -1.,
                          1. if nav['prepare_targets'] else -1., float(r['leader_present']),
                          1. / (1. + r['ttc']) if r['ttc'] is not None else 0.,
                          min(r['required_decel'] / self.max_decel, 1.) if r['required_decel'] is not None else 0.,
                          float(r['overlap']),
                          min(traci.lane.getMaxSpeed(traci.vehicle.getLaneID(self.ego_id)) / self.vmax, 1.)]
        return obs

    def _apply_lane_change(self, lane_change):
        v = traci.vehicle
        edge = v.getRoadID(self.ego_id)
        target = v.getLaneIndex(self.ego_id) + lane_change
        reason = ('internal_edge' if edge.startswith(':') else
                  'lane_bounds' if target < 0 or target >= traci.edge.getLaneNumber(edge) else
                  'solid_boundary' if lane_change and edge in self.solid else
                  'safety_gate' if lane_change and self.lc_safety_enabled and not self._lane_change_is_safe(lane_change) else
                  'other_rejection')
        applied = super()._apply_lane_change(lane_change)
        self.action_reason = ('keep' if lane_change == 0 else 'command_accepted') if applied else reason
        return applied

    def step(self, action):
        self.action_reason = 'ego_missing'
        before = risk()
        obs, reward, done, cut, info = super().step(action)
        info['ic_event']['risk_before_action'] = before
        info['ic_event']['lane_command_result'] = self.action_reason
        info['ic_event']['action_gate_enabled'] = self.lc_safety_enabled
        return obs, reward, done, cut, info


def environment(mode, seed):
    tree = ET.parse(SCENARIO / 'network.net.xml').getroot()
    edges = {e.get('id'): e for e in tree.findall('edge') if e.get('function') != 'internal'}
    routes = {e.get('id'): e.get('edges').split() for e in ET.parse(SCENARIO / 'highway.rou.xml').findall('route') if e.get('id', '').startswith('route_')}
    connections = [(c.get('from'), c.get('to'), int(c.get('fromLane')), int(c.get('toLane'))) for c in tree.findall('connection') if c.get('from') in edges and c.get('to') in edges]
    lengths = {k: max(float(l.get('length')) for l in e.findall('lane')) for k, e in edges.items()}
    internal = {l.get('id'): float(l.get('length')) for e in tree.findall('edge') if e.get('function') == 'internal' for l in e.findall('lane')}
    links = {}
    for c in tree.findall('connection'):
        key = c.get('from'), c.get('to')
        links[key] = max(links.get(key, 0.), internal.get(c.get('via'), 0.))
    nav = RouteNavigation({k: len(e.findall('lane')) for k, e in edges.items()}, connections, lengths, link_lengths=links)
    road = dict(ROAD, routes=routes, edges=[(k, e.get('from'), e.get('to'), len(e.findall('lane'))) for k, e in edges.items()], connections=connections,
                solid_lane_edges=[k for k, e in edges.items() if any(l.get('changeLeft') or l.get('changeRight') for l in e.findall('lane'))])
    action = copy.deepcopy(ACTION)
    action['lane_change_safety']['enabled'] = mode == 'action'
    reward = dict(REWARD)
    if mode == 'reward':
        reward['time_gap_s'] = 1.5
    ic.ZIP = ()  # Legacy Sano reward detector does not describe this map.
    ic.RAMPS = {k for k, e in edges.items() if e.get('type', '').endswith('_link')}
    env = ExperimentEnv(str(SCENARIO / 'run.sumocfg'), road, dict(EGO, depart_lane='best', depart_speed='max'),
                        dict(SIMULATION, warmup_steps=4500, max_steps=54000), OBSERVATION, action, reward,
                        dict(TRAFFIC, prefill={'enabled': False}), (), seed, navigation=nav, mode=mode)
    env.insert_wait_steps = 54000
    return env


class Log(RunLogger):
    def __init__(self, out, agent, start):
        super().__init__(str(out))
        self.out, self.agent, self.start, self.next_save = out, agent, start, 20000

    def log_train(self, step, metrics, verbose=True):
        super().log_train(step, metrics, verbose)
        self.agent.save(str(self.out / 'latest.pt'))
        self.save_csv()
        elapsed = time.perf_counter() - self.start
        save(self.out / 'progress.json', dict(steps=step, elapsed_seconds=elapsed,
             estimated_800k_hours=elapsed / step * 800000 / 3600))
        print(f'Elapsed {elapsed/60:.1f} min; estimated 800k {elapsed/step*800000/3600:.2f} hours', flush=True)
        if step >= self.next_save:
            self.agent.save(str(self.out / f'policy-{step}.pt'))
            self.next_save += 20000


def evaluate(env, agent, out, count, routes=None):
    rows = []
    start = time.perf_counter()
    for route in routes or env.routes:
        for i in range(count):
            row = dict(route=route, seed=9101+i, outcome='insertion_failure')
            try:
                obs, _ = env.reset(seed=9101+i, options={'route': route})
                teleports = 0
                while True:
                    obs, _, done, cut, info = env.step(agent.predict(obs, deterministic=True))
                    teleports += traci.simulation.getStartingTeleportNumber()
                    if done or cut:
                        break
                row.update(outcome='collision' if info['collided'] else 'arrival' if info['arrived'] and not teleports else 'teleport' if teleports else 'timeout' if cut else 'other', seconds=env.step_count*env.step_length)
            except RuntimeError as exc:
                if '삽입 실패' not in str(exc):
                    raise
                row['error'] = str(exc)
            rows.append(row)
            save(out / 'evaluation.json', rows)
    n = len(rows)
    save(out / 'summary.json', dict(cases=n, arrivals=sum(r['outcome']=='arrival' for r in rows),
         collisions=sum(r['outcome']=='collision' for r in rows), outcomes={k:sum(r['outcome']==k for r in rows) for k in sorted({r['outcome'] for r in rows})},
         completion_rate=sum(r['outcome']=='arrival' for r in rows)/n, collision_rate=sum(r['outcome']=='collision' for r in rows)/n,
         evaluation_seconds=time.perf_counter()-start, evaluated_routes=sorted({r['route'] for r in rows}), scope='Selected routes x count; fixed cases, not statistical proof'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['train', 'eval', 'collect'])
    p.add_argument('--mode', choices=['baseline', 'observation', 'action', 'reward'], default='baseline')
    p.add_argument('--steps', type=int, default=800000)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model', type=Path)
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--routes', nargs='+', help='Evaluation subset; omit for all 16 routes')
    args = p.parse_args()
    if args.steps < 2 or args.count < 1 or args.threads < 1:
        p.error('steps >= 2, count >= 1, threads >= 1 required')
    if args.command != 'train' and (not args.model or not args.model.is_file()):
        p.error('eval/collect require an existing --model')
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    hp = dict(HPARAMS, device='cpu', seed=args.seed)
    if args.model:
        meta_path = args.model.parent / 'manifest.json'
        if not meta_path.is_file():
            p.error('Model must have its original manifest.json beside it')
        old = json.loads(meta_path.read_text(encoding='utf8'))
        if old['mode'] != args.mode or old['input_hashes'] != {n:digest(SCENARIO/n) for n in old['input_hashes']}:
            p.error('Model mode or frozen scenario differs from its training manifest')
    model_step = None
    if args.model:
        if args.model.stem.startswith('policy-'):
            model_step = int(args.model.stem.split('-')[-1])
        elif args.model.name == 'model.pt' and (args.model.parent/'complete.json').is_file():
            model_step = json.loads((args.model.parent/'complete.json').read_text())['steps']
        elif args.model.name == 'latest.pt' and (args.model.parent/'progress.json').is_file():
            model_step = json.loads((args.model.parent/'progress.json').read_text())['steps']
    env = environment(args.mode, args.seed)
    if args.routes and (args.command != 'eval' or len(set(args.routes)) != len(args.routes) or not set(args.routes) <= set(env.routes)):
        p.error('--routes must be unique known evaluation routes')
    agent = PPO(obs_dim=47, act_dim=2, **hp)
    agent.save(str(args.out / 'initial.pt'))
    save(args.out / 'manifest.json', dict(command=args.command, mode=args.mode, seed=args.seed,
         source_hashes={p:digest(ROOT/p) for p in ['utils/ljj_experiment.py','env/sumo_env.py','env/ic_experiment.py','env/navigation_observation.py','env/navigation_clarity.py','algorithms/ppo.py','utils/buffer.py','train.py','env/mdp_config.py']},
         evaluation_routes=args.routes or list(env.routes), hparams=hp, steps=args.steps if args.command=='train' else None, model_step=model_step, evaluation_count=args.count, observation_schema='navigation47-risk-v1' if args.mode=='observation' else 'navigation47-baseline',
         scenario=str(SCENARIO.relative_to(ROOT)), input_hashes={n:digest(SCENARIO/n) for n in ['network.net.xml','highway.rou.xml','run.sumocfg']},
         git=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
         model=str(args.model) if args.model else None, model_sha=digest(args.model) if args.model else None,
         warmup_seconds=900, max_drive_seconds=10800, insert_limit_seconds=10800,
         action_gate=args.mode=='action', time_gap_s=1.5 if args.mode=='reward' else None,
         note='Fresh training; no optimizer/RNG continuation. Separate category ablations.'))
    try:
        if args.command == 'train':
            logger = Log(args.out, agent, time.perf_counter())
            try:
                agent.learn(env, args.steps, logger=logger, eval_interval=0, exact_budget=True)
                agent.save(str(args.out / 'model.pt'))
                save(args.out / 'complete.json', dict(steps=agent.num_timesteps, model_sha=digest(args.out/'model.pt')))
            finally:
                logger.close()
        elif args.command == 'eval':
            agent.load(str(args.model))
            evaluate(env, agent, args.out, args.count, args.routes)
        else:
            from types import SimpleNamespace
            from collect_pomdp_data import collect
            collect(SimpleNamespace(seed=args.seed, workers=1, policy='ppo', model=str(args.model), device='cpu', stochastic=False, gui=False, ndigits=4, episodes=args.count),
                    None, list(range(args.count)), 0, str(args.out/'transitions.jsonl.gz'), str(args.out/'transitions.npz'), env_factory=lambda:env)
    finally:
        env.close()


if __name__ == '__main__':
    main()

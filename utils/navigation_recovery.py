"""Navigation-only replay diagnostics. No forced actions or environment edits."""
import argparse
import collections
import concurrent.futures
import os
import time
from utils import resume_validation as r

b, f = r.b, r.f
OUT = f.ROOT / 'results/navigation_recovery_20261113'
ROUTES = ['route_01', 'route_02', 'route_10', 'route_11', 'route_13', 'route_14', 'route_15', 'route_16']


class AuditEnv(r.c.ClarityEnv):
    def _apply_lane_change(self, direction):
        v = b.traci.vehicle
        edge = v.getRoadID(self.ego_id)
        nav = self.navigation_context()
        lane = v.getLaneIndex(self.ego_id)
        reason = 'keep'
        if direction:
            if edge.startswith(':'): reason = 'internal_junction'
            elif edge in self.solid: reason = 'solid_marking'
            elif not 0 <= lane + direction < b.traci.edge.getLaneNumber(edge): reason = 'outside_road'
            elif self.lc_safety_enabled and not self._lane_change_is_safe(direction):
                reason = 'entry_protection' if v.getLanePosition(self.ego_id) < self.lc_spawn_protect else 'unsafe_gap'
            else: reason = 'request_allowed'
        allowed = super()._apply_lane_change(direction)
        key = (edge, reason)
        self.audit_counts[key] += 1
        targets = nav['prepare_targets']
        if targets and lane not in targets:
            self.unready_counts[reason] += 1
        self.last_request = dict(edge=edge, lane=lane, direction=int(direction), reason=reason,
                                 accepted=bool(allowed), targets=targets, distance=nav['distance'])
        return allowed

    def reset(self, *args, **kwargs):
        self.audit_counts = collections.Counter()
        self.unready_counts = collections.Counter()
        self.last_request = None
        return super().reset(*args, **kwargs)


def environment(seed, load, cls=AuditEnv, lane="best", speed="max"):
    m = f.read(r.sources('baseline', seed) / 'manifest.json')
    return cls(str(OUT / 'traffic_v2' / load / 'run.sumocfg'),
               dict(b.ROAD_NEW, routes=b.MAN['routes']),
               dict(m['ego'], depart_lane=str(lane), depart_speed=str(speed)),
               dict(m['simulation'], warmup_steps=300), b.OBSERVATION, m['action'], m['reward'],
               dict(b.TRAFFIC, prefill={'enabled': False}), (), seed, navigation=b.NAV, clarity='baseline')


def job(spec):
    seed, load, smoke, hard = spec
    b.torch.set_num_threads(1)
    dest = OUT / ('smoke' if smoke else 'hard-starts' if hard else 'diagnostics') / f'{load}-{seed}'
    if (dest / 'complete.json').exists(): return str(dest)
    dest.mkdir(parents=True, exist_ok=True)
    model = r.sources('baseline', seed) / 'policy-600064.pt'
    meta = f.read(model.parent / 'manifest.json')
    agent = b.PPO(obs_dim=47, act_dim=2, **meta['hp'])
    agent.load(str(model))
    r.save(dest / 'manifest.json', dict(source=str(model), source_sha=b.digest(model),
           map_sha=b.digest(b.MAP / 'network.net.xml'), commit=b.COMMIT, load=load, seed=seed,
           start="last_lane_15mps" if hard else "best_max", forced_correction=False, reward=meta['reward'], action=meta['action'], hp=meta['hp']))
    rows = []
    for route in (['route_13'] if smoke else ROUTES):
        e = environment(seed, load, lane=str(f.COUNTS[b.MAN['routes'][route][0]]-1) if hard else "best", speed="15" if hard else "max")
        try:
            obs, _ = e.reset(seed=40001, options={'route': route})
            trace = b.TimeoutTrace()
            teleports = 0
            samples = []
            while True:
                if e.step_count % 5 == 0:
                    trace.sample(e)
                    v = b.traci.vehicle
                    leader = v.getLeader(e.ego_id, 200)
                    samples.append(dict(t=e.step_count*e.step_length, nav=e.navigation_context(),
                        lane=v.getLaneID(e.ego_id), speed=v.getSpeed(e.ego_id),
                        limit=b.traci.lane.getMaxSpeed(v.getLaneID(e.ego_id)),
                        leader=leader, leader_speed=v.getSpeed(leader[0]) if leader else None,
                        request=e.last_request))
                obs, _, done, cut, info = e.step(agent.predict(obs, deterministic=True))
                teleports += b.traci.simulation.getStartingTeleportNumber()
                if done or cut: break
            assert e.route_override_count == 0
            diagnosis = trace.result()
            outcome = ('collision' if info['collided'] else 'teleport' if teleports else
                       'arrival' if info['arrived'] else diagnosis['category'])
            rows.append(dict(route=route, outcome=outcome, seconds=e.step_count*e.step_length,
                             diagnostic=diagnosis, unready_commands=dict(e.unready_counts),
                             commands=[dict(edge=k[0], reason=k[1], count=n) for k,n in e.audit_counts.items()]))
            r.save(dest / f'{route}.trace.json', samples)
            r.save(dest / 'evaluation.json', rows)
            r.save(dest / 'progress.json', dict(pid=os.getpid(), completed=len(rows), updated=time.time()))
        finally:
            e.close()
    r.save(dest / 'complete.json', dict(cases=len(rows), outcomes=dict(collections.Counter(x['outcome'] for x in rows))))
    return str(dest)


def main():
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');p.add_argument('--hard-starts',action='store_true');args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'active.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        f.OUT=OUT
        for load in ['none','low']: f.prepare(load)
        specs=[(11,'none',True,False)] if args.smoke else [(s,l,False,args.hard_starts) for s in [11,22,33] for l in (['none'] if args.hard_starts else ['none','low'])]
        r.save(OUT/'status.json',dict(stage='diagnosing',pid=os.getpid(),jobs=len(specs)))
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
            for result in pool.map(job,specs): print(result,flush=True)
        r.save(OUT/'status.json',dict(stage='diagnostics_complete',jobs=len(specs)))
    except Exception as exc:
        r.save(OUT/'status.json',dict(stage='error',error=repr(exc)));raise
    finally: lock.unlink(missing_ok=True)


if __name__=='__main__': main()

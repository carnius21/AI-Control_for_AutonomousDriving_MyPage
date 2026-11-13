"""Read-only timeout diagnosis; never changes policies, traffic or episode limits."""
from collections import deque
from env.sumo_env import traci

class TimeoutTrace:
    def __init__(self):
        self.samples = deque(maxlen=60)
    def sample(self, env):
        v = traci.vehicle
        if env.ego_id not in v.getIDList(): return
        edge = v.getRoadID(env.ego_id)
        lane = v.getLaneID(env.ego_id)
        idx = v.getRouteIndex(env.ego_id)
        route = env.routes[env.episode_route]
        nxt = route[idx+1] if 0 <= idx < len(route)-1 else None
        allowed = sorted(env.links.get(edge, {}).get(nxt, []))
        leader = v.getLeader(env.ego_id, 100.)
        self.samples.append(dict(seconds=env.step_count*env.step_length, edge=edge, lane=lane,
            lane_index=v.getLaneIndex(env.ego_id), position=v.getLanePosition(env.ego_id),
            remaining=traci.lane.getLength(lane)-v.getLanePosition(env.ego_id),
            speed=v.getSpeed(env.ego_id), next_edge=nxt, allowed_lanes=allowed,
            leader_gap=leader[1] if leader else None,
            leader_speed=v.getSpeed(leader[0]) if leader else None))
    def result(self):
        rows=list(self.samples)
        if not rows: return dict(category='unknown', samples=[])
        def frac(fn): return sum(bool(fn(r)) for r in rows)/len(rows)
        wrong=lambda r: bool(r['allowed_lanes']) and r['lane_index'] not in r['allowed_lanes']
        route_stop=frac(lambda r: wrong(r) and r['remaining']<=10 and r['speed']<.5)
        queue=frac(lambda r: r['speed']<2 and r['leader_gap'] is not None and r['leader_gap']<25 and r['leader_speed']<2)
        moving=frac(lambda r:r['speed']>=2)
        category=('route_lane_blocked' if route_stop>=.8 else 'queue_with_slow_leader' if queue>=.8 else 'moving_at_timeout' if moving>=.8 else 'mixed_or_unexplained')
        return dict(category=category, window_seconds=rows[-1]['seconds']-rows[0]['seconds'],
            route_stop_fraction=route_stop, queue_fraction=queue, moving_fraction=moving,
            mean_speed=sum(r['speed'] for r in rows)/len(rows), samples=rows)

"""Route-balanced IC episodes for the shared PPO policy and POMDP collector."""
from collections import defaultdict
import numpy as np
from gymnasium import spaces
from env.sumo_env import SumoHighwayEnv, traci

ZIP = ("sano_nb_to_west", "sano_sb_to_west")
# Simulation ramp limits are the active lane speed limits from the integrated map.
RAMPS = {"east_join", "east_ramp", "north_loop", "south_loop", "south_loop_bridge",
         "south_loop_join", "north_exit", "south_exit", "flyover", *ZIP}

class ICExperimentEnv(SumoHighwayEnv):
    def __init__(self, cfg, road, ego, sim, obs, action, reward, traffic, variants=(), seed=11):
        self.variants = set(variants)
        rw = dict(reward)
        if "BLOCK" in self.variants: rw["blocked_penalty"] = 0
        if "GAP" in self.variants: rw["time_gap_s"] = 1.
        super().__init__(cfg, road, ego, sim, obs, action, rw, traffic=traffic)
        self.insert_wait_steps = round(120/self.step_length)
        self.routes = road["routes"]
        self.route_rng = np.random.default_rng(seed)
        self.schedule = []
        self.counts = {edge[0]: edge[3] for edge in road["edges"]}
        self.links = defaultdict(lambda: defaultdict(set))
        for src,dst,lane,_ in road["connections"]: self.links[src][dst].add(lane)
        self.solid = set(road.get("solid_lane_edges", ()))
        self.obs_dim += 6
        self.observation_space = spaces.Box(-1, 1, (self.obs_dim,), np.float32)

    def reset(self, seed=None, options=None):
        opts = options or {}
        if "route" in opts:
            self.episode_route = opts["route"]
        else:
            if not self.schedule: self.schedule = list(self.route_rng.permutation(list(self.routes)))
            self.episode_route = str(self.schedule.pop())
        self.sumo_seed = int(seed if seed is not None else self.route_rng.integers(1, 2**30))
        self.last_zip_side = None
        self.prep_scored = set()
        self.route_lane_scored = set()
        if getattr(self, "load_paths", None):
            if not self.load_schedule:
                self.load_schedule=list(self.route_rng.permutation(sorted(self.load_paths)))
            self.cfg_path=self.load_paths[self.load_schedule.pop()]
        self.zips = 0
        return super().reset(seed=seed)

    def _apply_lane_change(self, lane_change):
        if "START1" in self.variants and self.step_count * self.step_length < 1.:
            return False
        if lane_change and traci.vehicle.getRoadID(self.ego_id) in self.solid: return False
        return super()._apply_lane_change(lane_change)

    def _route_lane_ready(self):
        """Score actual route-compatible lanes once per split, including short links."""
        v = traci.vehicle
        edge = v.getRoadID(self.ego_id)
        idx = v.getRouteIndex(self.ego_id)
        path = self.routes[self.episode_route]
        if idx < 0 or idx + 1 >= len(path) or len(self.links.get(edge, {})) < 2:
            return None
        target = self.links[edge].get(path[idx+1])
        if not target or len(target) == self.counts[edge] or idx in self.route_lane_scored:
            return None
        left = traci.lane.getLength(v.getLaneID(self.ego_id)) - v.getLanePosition(self.ego_id)
        if left > 100:
            return None
        self.route_lane_scored.add(idx)
        return v.getLaneIndex(self.ego_id) in target

    def context(self):
        v = traci.vehicle
        e = v.getRoadID(self.ego_id)
        lane = v.getLaneIndex(self.ego_id)
        lane_id = v.getLaneID(self.ego_id)
        limit = traci.lane.getMaxSpeed(lane_id)
        path = self.routes[self.episode_route]
        idx = v.getRouteIndex(self.ego_id)
        distance = None
        offset = 0
        split = None
        if idx >= 0 and not e.startswith(":"):
            for j in range(idx, len(path)-1):
                src, dst = path[j:j+2]
                targets = self.links[src][dst]
                if len(self.links[src]) < 2 or len(targets) != 1 or 0 not in targets or self.counts[src] < 2:
                    continue
                distance = v.getDrivingDistance(self.ego_id, src, traci.lane.getLength(src+"_0")-.01, 0)
                if distance < 0: distance = None
                split = src
                offset = -lane
                break
        best = next((r[3] for r in v.getBestLanes(self.ego_id) if r[0]==lane_id),0)
        return e, lane, limit, distance, split, offset, best

    def approach(self, side):
        lane = side+"_0"
        length = traci.lane.getLength(lane)
        return {v for v in traci.lane.getLastStepVehicleIDs(lane)
                if length-traci.vehicle.getLanePosition(v) <= 45}

    def _get_obs(self):
        base = super()._get_obs()
        if len(base)==self.obs_dim: return base  # terminal
        e,_,limit,dist,_,offset,best = self.context()
        other = bool(self.approach(ZIP[1-ZIP.index(e)])) if e in ZIP else False
        return np.append(base, [np.clip(best/3,-1,1), min(dist/200,1) if dist is not None else -1,
                                np.clip(offset/3,-1,1), min(limit/self.vmax,1), float(e in RAMPS),
                                (1. if self.last_zip_side==e else .5) if other else 0.]).astype(np.float32)

    def step(self, action):
        before = self.context()
        edge,lane,limit,distance,split,offset,_ = before
        contenders = [self.approach(s) for s in ZIP]
        obs,r,done,cut,info = super().step(action)
        alive = self.ego_id in traci.vehicle.getIDList()
        after = self.context() if alive else None
        arrived = info["arrived"] and not info["collided"] and edge==self.routes[self.episode_route][-1]
        info["arrived"] = bool(arrived)
        if done and not info["collided"] and not arrived: r = 0.
        bonus = 0.
        components = dict(route=0., zipper=0., ramp=0.)
        prep = None
        lane_distance = None
        route_ready = None
        if after:
            if self.variants.intersection(("ROUTE100", "MEASURE_ROUTE")):
                route_ready = self._route_lane_ready()
                if route_ready is not None and "ROUTE100" in self.variants:
                    components["route"] = .1 if route_ready else -.1
                    bonus += components["route"]
            e2,l2,limit2,d2,s2,off2,_ = after
            if edge==e2 and split==s2 and lane!=l2 and l2==0: lane_distance=d2
            if split and split==s2 and d2 is not None and distance is not None and distance>100>=d2 and split not in self.prep_scored:
                self.prep_scored.add(split)
                prep = off2==0
                if "PREP" in self.variants and prep: bonus += .1
        # Identify actual entry onto the internal merge link. Simultaneous entries
        # cannot establish order, so exclude them from compliance scoring.
        passed = []
        for side,ids in zip(ZIP,contenders):
            for v in ids:
                if v in traci.vehicle.getIDList():
                    road = traci.vehicle.getRoadID(v)
                    if road.startswith(":sano_local_merge") or road=="sano_west_ramp_split":
                        passed.append((side,v))
        zipper = None
        if len(passed)==1:
            side,vid = passed[0]
            if vid==self.ego_id:
                self.zips += 1
                if all(contenders) and self.last_zip_side is not None:
                    zipper = int(side!=self.last_zip_side)
                    if "ZIP" in self.variants:
                        components["zipper"] = .1 if zipper else -.1
                        bonus += components["zipper"]
            self.last_zip_side = side
        elif passed: self.last_zip_side = None
        overspeed = 0.
        if after and after[0] in RAMPS:
            overspeed = max(0.,info["speed"]-after[2])
            if "RAMP" in self.variants:
                components["ramp"] = -.1*(overspeed/after[2])*self.step_length/.5
                bonus += components["ramp"]
        scale = .25 if "SCALE025" in self.variants else 1.
        bonus *= scale
        components = {k: v*scale if not done else 0. for k,v in components.items()}
        if not done: r = r*self.step_length/.5 + bonus
        event=dict(route=self.episode_route,sumo_seed=self.sumo_seed,prep100=prep,route_lane_ready=route_ready,
                   exit_lane_change_distance_m=lane_distance,zipper_count=self.zips,
                   zipper_compliant=zipper,ramp=bool(after and after[0] in RAMPS),
                   ramp_excess_mps=overspeed,wrong_exit=bool(done and not arrived and not info["collided"]))
        event["reward_components"] = dict(base=r-sum(components.values()), **components)
        info["ic_event"] = event
        return obs,r,done,cut,info

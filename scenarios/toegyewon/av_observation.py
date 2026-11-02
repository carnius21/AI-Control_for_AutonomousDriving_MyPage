"""Local traffic features plus route-aware lane guidance on a branching net.

The first 31 slots follow env/mdp_config.py's layout. No SumoHighwayEnv
instance, fixed r0, world-X distance or global number of lanes is used.
"""

import numpy as np

OFFSETS = (2, 1, 0, -1, -2)
SCHEMAS = {"legacy": ("highway-layout31-adapter-v1", 31),
           "route": ("toegyewon-route43-v1", 43)}


class RouteObservation:
    def __init__(self, connection, ego_id, config):
        self.c, self.ego_id, self.config = connection, ego_id, config
        self.visibility = float(config.get("visibility", 50))
        self.vmax = float(config.get("speed_normalization", 33.33))
        self.mode = config.get("observation", "route")
        self.schema, self.dim = SCHEMAS[self.mode]

    def observe(self):
        c, ego = self.c, self.ego_id
        edge = c.vehicle.getRoadID(ego)
        lane = c.vehicle.getLaneID(ego)
        index = c.vehicle.getLaneIndex(ego)
        position = c.vehicle.getLanePosition(ego)
        speed = c.vehicle.getSpeed(ego)
        route = list(c.vehicle.getRoute(ego))
        route_index = c.vehicle.getRouteIndex(ego)
        next_edge = route[route_index + 1] if route_index + 1 < len(route) else None
        internal = edge.startswith(":")
        best = {} if internal else {b[0]: b for b in c.vehicle.getBestLanes(ego)}
        count = c.edge.getLaneNumber(edge)
        remaining = max(0., c.lane.getLength(lane) - position)
        neighbors, connectivity, density, reachability = [], [], [], []
        obs = [speed / self.vmax]
        for offset in OFFSETS:
            target = index + offset
            exists = 0 <= target < count
            lane_id = f"{edge}_{target}"
            candidates = []
            if exists:
                for vid in c.lane.getLastStepVehicleIDs(lane_id):
                    if vid == ego:
                        continue
                    d = c.vehicle.getLanePosition(vid) - position
                    if abs(d) <= self.visibility:
                        candidates.append((vid, d - c.vehicle.getLength(vid) if d >= 0 else d + c.vehicle.getLength(ego), d >= 0))
            # TraCI handles leaders across connected edge/internal-lane boundaries.
            if offset == 0:
                for leading, pair in [(True, c.vehicle.getLeader(ego, self.visibility)),
                                      (False, c.vehicle.getFollower(ego, self.visibility))]:
                    if pair and pair[0] and pair[1] <= self.visibility:
                        candidates.append((pair[0], pair[1] if leading else -pair[1], leading))
            elif abs(offset) == 1 and exists and not internal:
                for leading in (True, False):
                    mode = (2 if leading else 0) + (1 if offset == -1 else 0)
                    for vid, gap in c.vehicle.getNeighbors(ego, mode):
                        if gap <= self.visibility:
                            candidates.append((vid, gap if leading else -gap, leading))
            for leading in (True, False):
                items = [p for p in candidates if p[2] == leading]
                if not items:
                    obs.extend([1., 1.] if leading else [-1., -1.])
                    continue
                vid, gap, _ = min(items, key=lambda p: p[1] if leading else -p[1])
                bumper_gap = gap if leading else -gap
                signed_gap = max(0., bumper_gap) * (1 if leading else -1)
                other_speed = c.vehicle.getSpeed(vid)
                obs.extend([signed_gap / self.visibility, (other_speed - speed) / self.vmax])
                neighbors.append({"id": vid, "type": c.vehicle.getTypeID(vid),
                                  "length": c.vehicle.getLength(vid), "lane_offset": offset,
                                  "gap": signed_gap, "bumper_gap": bumper_gap,
                                  "longitudinal_overlap": bumper_gap < 0,
                                  "leader": leading, "speed": other_speed,
                                  "relative_speed": other_speed - speed,
                                  "position_xy": list(c.vehicle.getPosition(vid))})
            if not exists:
                connectivity.append(-1.)
                density.append(1.)
                reachability.append(-1.)
                continue
            links = c.lane.getLinks(lane_id)
            connectivity.append(1. if links else min(1., remaining / self.visibility))
            count_ahead = sum(c.vehicle.getLanePosition(v) > position for v in c.lane.getLastStepVehicleIDs(lane_id)
                              if v != ego and c.vehicle.getLanePosition(v) - position <= self.visibility)
            # Follow this route's connection, never an arbitrary first branch.
            selected = next((link[0] for link in links if link[0].rsplit("_", 1)[0] == next_edge), None)
            if selected and remaining < self.visibility:
                count_ahead += sum(c.vehicle.getLanePosition(v) <= self.visibility - remaining
                                   for v in c.lane.getLastStepVehicleIDs(selected))
            density.append(min(1., count_ahead * 7.5 / max(1., min(self.visibility, remaining) if not links else self.visibility)))
            reachability.append(1. if next_edge is None or selected else 0.)
        obs += connectivity + density
        current_best = best.get(lane)
        best_offset = int(current_best[3]) if current_best else 0
        # SUMO bestLanes offset points towards the preferred lane.
        best_distance = max(0., current_best[1] - position) if current_best else remaining
        if self.mode == "route":
            obs += reachability + [remaining / self.visibility, best_offset / 4,
                                   index / max(1, count - 1), route_index / max(1, len(route) - 1),
                                   c.vehicle.getAllowedSpeed(ego) / self.vmax, float(internal),
                                   best_distance / self.visibility]
        info = {"edge": edge, "lane": lane, "lane_index": index, "position": position,
                "position_xy": list(c.vehicle.getPosition(ego)), "speed": speed,
                "acceleration": c.vehicle.getAcceleration(ego),
                "route": route, "route_index": route_index, "next_edge": next_edge,
                "destination": route[-1], "distance_travelled": c.vehicle.getDistance(ego),
                "remaining_edge_m": remaining, "best_lane_offset": best_offset,
                "best_lane_distance_m": best_distance, "target_lane": index + best_offset,
                "route_lane_reachability": reachability, "neighbors": neighbors,
                "speed_mode": c.vehicle.getSpeedMode(ego), "lane_change_mode": c.vehicle.getLaneChangeMode(ego)}
        return np.clip(np.array(obs, dtype=np.float32), -1, 1), info


def apply_safe_action(c, ego, action, state, config, forbidden):
    """PPO proposal + explicit route/gap/permission gate + SUMO safety checks.

    SUMO strategic/cooperative changes stay enabled (1621). A zero lane action
    never pins the lane. Submitted requests are not counted as completed changes.
    """
    action = np.asarray(action, dtype=float)
    if action.shape != (2,) or not np.isfinite(action).all():
        raise ValueError("AV action must be two finite values")
    raw = np.clip(action, -1, 1)
    accel = float(raw[0]) * (c.vehicle.getAccel(ego) if raw[0] >= 0 else c.vehicle.getDecel(ego))
    target_speed = max(0., min(c.vehicle.getAllowedSpeed(ego), state["speed"] + accel * c.simulation.getDeltaT()))
    c.vehicle.setSpeed(ego, target_speed)
    direction = 1 if raw[1] >= .5 else -1 if raw[1] <= -.5 else 0
    event = {"raw": raw.tolist(), "requested_accel": accel, "requested_speed": target_speed,
             "lane_direction": direction, "lane_request_submitted": False, "rejection": None}
    if not direction:
        return event
    edge, target = state["edge"], state["lane_index"] + direction
    if edge.startswith(":") or edge in forbidden:
        event["rejection"] = "junction_or_lane_change_prohibited"
    elif "passenger" not in c.lane.getChangePermissions(state["lane"], direction):
        event["rejection"] = "lane_permission"
    elif not 0 <= target < c.edge.getLaneNumber(edge):
        event["rejection"] = "no_target_lane"
    elif (state["best_lane_offset"] and state["best_lane_distance_m"] <= config.get("route_guard_distance", 50)
          and direction * state["best_lane_offset"] < 0):
        event["rejection"] = "away_from_route_lane"
    elif (state["remaining_edge_m"] <= config.get("route_guard_distance", 50)
          and state["route_lane_reachability"][OFFSETS.index(direction)] == 0
          and state["route_lane_reachability"][OFFSETS.index(0)] == 1):
        event["rejection"] = "target_lane_misses_route"
    else:
        target_lane = f"{edge}_{target}"
        minimum = config.get("min_lane_change_gap", 3)
        tau = config.get("lane_change_headway", .5)
        unsafe = False
        # Same-edge geometric gaps use real bus length. Include TraCI neighbors
        # to cover target-lane followers/leaders near a junction.
        for v in c.lane.getLastStepVehicleIDs(target_lane):
            d = c.vehicle.getLanePosition(v) - state["position"]
            gap = d - c.vehicle.getLength(v) if d >= 0 else -d - c.vehicle.getLength(ego)
            required = minimum + tau * (state["speed"] if d >= 0 else c.vehicle.getSpeed(v))
            unsafe |= gap < required
        for neighbor in state["neighbors"]:
            if neighbor["lane_offset"] == direction:
                unsafe |= neighbor["bumper_gap"] < minimum + tau * max(state["speed"], neighbor["speed"])
        # SUMO lane-change blocked flags: overlap, insufficient front/rear gaps.
        model_state, _ = c.vehicle.getLaneChangeState(ego, direction)
        unsafe |= bool(model_state & (2**9 | 2**10 | 2**11 | 2**12 | 2**13))
        if unsafe:
            event["rejection"] = "insufficient_gap"
        else:
            c.vehicle.changeLane(ego, target, config.get("lane_change_duration", 1.0))
            event["lane_request_submitted"] = True
    return event

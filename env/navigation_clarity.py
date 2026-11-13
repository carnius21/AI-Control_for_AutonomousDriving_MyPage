"""Observation-only ablation. Parent actions, rewards and road stay unchanged."""
import numpy as np
from gymnasium import spaces
from env.navigation_observation import NavigationEnv
from env.sumo_env import traci


def validity_features(nav):
    return [1. if nav['current_targets'] else -1.,
            1. if nav['prepare_targets'] else -1.]


def second_constraint_features(nav, path, index, remaining, internal=False):
    absent = [-1., 0., 0., 0., 0., 0., 0., -1.]
    if internal or index < 0:
        return absent
    distance, found = max(0., remaining), 0
    for j in range(index, len(path)-1):
        if distance > nav.horizon:
            break
        edge, nxt = path[j:j+2]
        targets = {a for a, b in nav.links[edge, nxt]}
        if targets and len(targets) < nav.counts[edge]:
            found += 1
            if found == 2:
                assert nav.counts[edge] <= 6, 'Schema supports up to six future lanes'
                mask = [1. if i in targets else -1. if i < nav.counts[edge] else 0. for i in range(6)]
                return [distance/nav.horizon, *mask, 1.]
        distance += nav.link_lengths.get((edge,nxt),0.) + nav.lengths[nxt]
    return absent


class ClarityEnv(NavigationEnv):
    def __init__(self, *args, clarity='baseline', **kwargs):
        assert clarity in ('baseline', 'validity', 'lookahead')
        self.clarity = clarity
        super().__init__(*args, observation_mode='N1', **kwargs)
        # Keep parent obs_dim=37: its terminal and IC append logic uses this value.
        # Only the exposed policy space is extended.
        self.observation_space = spaces.Box(-1, 1, (47,), np.float32)

    def _get_obs(self):
        original = super()._get_obs()
        extra = np.zeros(10, dtype=np.float32)
        if self.clarity != 'baseline' and self.ego_id in traci.vehicle.getIDList():
            extra[:2] = validity_features(self.navigation_context())
            if self.clarity == 'lookahead':
                v = traci.vehicle
                extra[2:] = second_constraint_features(
                    self.navigation, self.routes[self.episode_route], v.getRouteIndex(self.ego_id),
                    traci.lane.getLength(v.getLaneID(self.ego_id))-v.getLanePosition(self.ego_id),
                    v.getRoadID(self.ego_id).startswith(':'))
        result = np.concatenate((original, extra)).astype(np.float32)
        assert result.shape == (47,) and np.isfinite(result).all()
        return result

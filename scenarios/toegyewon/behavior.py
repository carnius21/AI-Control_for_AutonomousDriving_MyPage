"""Deterministic observation-only baseline; not trained and not an expert."""

import numpy as np


class RouteHeuristic:
    version = "route-following-heuristic-v2"

    def __init__(self, observation_mode="route", visibility=50., speed_normalization=33.33):
        self.mode, self.visibility, self.vmax = observation_mode, visibility, speed_normalization

    def predict(self, observation, deterministic=True):
        o = np.asarray(observation)
        expected = 43 if self.mode == "route" else 31
        if o.shape != (expected,) or not np.isfinite(o).all():
            raise ValueError("Invalid heuristic observation")
        speed = float(o[0]) * self.vmax
        desired = .8 * float(o[40]) * self.vmax if expected == 43 else .7 * self.vmax
        # Current-lane leader is indices 9/10 in the shared 31-feature layout.
        if o[9] < .999:
            gap = max(0., float(o[9]) * self.visibility)
            leader_speed = max(0., speed + float(o[10]) * self.vmax)
            desired = min(desired, max(0., leader_speed + .8 * (gap - 3 - 1.2 * speed)))
        lane = 0.
        if expected == 43 and o[41] < .5 and abs(o[37]) > .01 and o[42] < .99:
            lane = float(np.sign(o[37]))
            # Reserve time for each required lane crossing on the short weave.
            crossings = max(1., abs(float(o[37])) * 4)
            desired = min(desired, max(1., float(o[42]) * self.visibility / (3 * crossings)))
        # Existing SUMO/gap/route safety gate remains the final authority.
        accel = np.clip(desired - speed, -4.5, 2.6)
        return np.asarray([accel / (2.6 if accel >= 0 else 4.5), lane], dtype=np.float32)

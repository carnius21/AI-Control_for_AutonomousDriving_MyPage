"""Gymnasium adapter for one route-aware AV; leaves the teaching highway intact.

controller='sumo' is a simulator baseline, never an RL result.
controller='external' accepts policy proposals subject to safety and route gates.
"""

import copy
import json
import math
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import traci
import traci.constants as tc

from .network import binary, write_demand
from .av_observation import RouteObservation, SCHEMAS, apply_safe_action


class ToegyewonEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, out, manifest, controller="sumo", name="av", vehicles=None,
                 background=True, gui=False, collect_state=False, record_trace=True):
        super().__init__()
        if controller not in ("sumo", "external"):
            raise ValueError("controller must be sumo or external")
        self.out, self.manifest = Path(out), copy.deepcopy(manifest)
        self.cfg = self.manifest["config"].setdefault("av", {})
        self.cfg["enabled"] = True
        for key, default in (("visibility", 50), ("speed_normalization", 33.33),
                             ("time_limit", 600), ("insertion_timeout", 180)):
            if not math.isfinite(float(self.cfg.get(key, default))) or float(self.cfg.get(key, default)) <= 0:
                raise ValueError(f"av.{key} must be finite and positive")
        if not math.isfinite(float(self.cfg.get("depart", 17.4))) or self.cfg.get("depart", 17.4) < 0:
            raise ValueError("av.depart must be finite and nonnegative")
        self.ego_id = self.cfg.get("id", "av_toegyewon")
        if self.ego_id in ("pink", "green") or self.ego_id.startswith(("flow_", "bus_")):
            raise ValueError("AV id must be distinct from test and background vehicles")
        self.route_id = self.cfg.get("route", "green")
        if self.route_id not in self.manifest["routes"]:
            raise ValueError(f"Unknown AV route: {self.route_id}")
        self.expected_route = self.manifest["routes"][self.route_id]
        self.controller, self.name, self.gui = controller, name, gui
        self.collect_state, self.record_trace = collect_state, record_trace
        self.vehicles, self.background = vehicles, background
        if vehicles is not None and sum(v["id"] == self.ego_id for v in vehicles) != 1:
            raise ValueError("An explicit vehicle list must contain exactly one AV with the configured ID")
        self.visibility = float(self.cfg.get("visibility", 50))
        self.schema, self.obs_dim = SCHEMAS[self.cfg.get("observation", "route")]
        self.observation_space = spaces.Box(-1., 1., (self.obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1., 1., (2,), dtype=np.float32)
        self.c = None
        self.files = []
        self.done = False

    def _tick(self):
        self.c.simulationStep()
        new = self.c.simulation.getDepartedIDList()
        self.departed.extend(new)
        if self.collect_state:
            for vid in new:
                self.c.vehicle.subscribe(vid, (tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_ACCELERATION,
                    tc.VAR_ROAD_ID, tc.VAR_LANE_ID, tc.VAR_LANE_INDEX, tc.VAR_LANEPOSITION,
                    tc.VAR_TYPE, tc.VAR_LENGTH, tc.VAR_ROUTE_ID, tc.VAR_ROUTE_INDEX, tc.VAR_EDGES,
                    tc.VAR_ALLOWED_SPEED))
        self.arrived.extend(self.c.simulation.getArrivedIDList())
        self.collisions.extend(self.c.simulation.getCollidingVehiclesIDList())
        self.teleports.extend(self.c.simulation.getStartingTeleportIDList())

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.close()
        if seed is not None:
            self.manifest["config"]["seed"] = seed
        self.departed, self.arrived, self.collisions, self.teleports = [], [], [], []
        self.visited, self.rejections, self.requested_changes = [], {}, 0
        self.done = False
        self.status = "waiting_for_insertion"
        self.last_state = {}
        self.last_obs = np.zeros(self.obs_dim, dtype=np.float32)
        self.steps = 0
        self.min_accel, self.speed_sum, self.harsh, self.in_harsh = 0., 0., 0, False
        self.weave_bus_neighbor_seconds = self.weave_car_neighbor_seconds = 0.
        self.weave_bus_leader_seconds = self.weave_braking_seconds = 0.
        self.weave_observed = False
        self.weave_enter = self.weave_exit = None
        self.actual_lane_changes = 0
        self.cfg_path = write_demand(self.out, self.manifest, self.vehicles, self.background, self.name)
        args = [binary("sumo-gui" if self.gui else "sumo"), "-c", str(self.cfg_path),
                "--no-step-log", "true", "--tripinfo-output", str(self.out / (self.name + ".trips.xml")),
                "--tripinfo-output.write-unfinished", "true",
                "--lanechange-output", str(self.out / (self.name + ".lanechanges.xml")),
                "--collision-output", str(self.out / (self.name + ".collisions.xml")),
                "--error-log", str(self.out / (self.name + ".errors.log"))]
        if self.gui:
            args += ["--quit-on-end", "false", "--start", "false"]
        log = (self.out / (self.name + ".sumo.log")).open("w", encoding="utf-8")
        self.trace = (self.out / (self.name + ".av.jsonl")).open("w", encoding="utf-8") if self.record_trace else None
        self.files = [log] + ([self.trace] if self.trace else [])
        try:
            label = "toegyewon-av-" + uuid.uuid4().hex
            traci.start(args, label=label, stdout=log, doSwitch=False)
            self.c = traci.getConnection(label)
            deadline = min(float(self.cfg.get("time_limit", 600)),
                           float(self.cfg.get("depart", 17.4)) + self.cfg.get("insertion_timeout", 180))
            while self.ego_id not in self.c.vehicle.getIDList() and self.c.simulation.getTime() < deadline:
                self._tick()
            if self.ego_id not in self.c.vehicle.getIDList():
                self.status = "insertion_timeout"
                self.done = True
                raise RuntimeError(f"AV was not safely inserted by {deadline}s")
            # Retain SUMO safety, strategic and cooperative lane-change behavior.
            self.c.vehicle.setSpeedMode(self.ego_id, 31)
            self.c.vehicle.setLaneChangeMode(self.ego_id, 1621)
            self.observer = RouteObservation(self.c, self.ego_id, self.cfg)
            self.status = "running"
            self.last_obs, self.last_state = self.observer.observe()
            self._record(None)
            return self.last_obs.copy(), self.last_state.copy()
        except Exception:
            self.close()
            raise

    def _record(self, action):
        state = self.last_state
        edge = state["edge"]
        if not edge.startswith(":") and (not self.visited or self.visited[-1] != edge):
            self.visited.append(edge)
        self.steps += 1
        acc = state["acceleration"]
        self.min_accel = min(self.min_accel, acc)
        self.speed_sum += state["speed"]
        hard = acc < self.manifest["config"].get("validation", {}).get("hard_braking_threshold", -4.5) - 1e-6
        self.harsh += int(hard and not self.in_harsh)
        self.in_harsh = hard
        if edge == "weave":
            self.weave_observed = True
            if self.weave_enter is None:
                self.weave_enter = self.c.simulation.getTime()
            self.weave_exit = self.c.simulation.getTime()
            dt = self.manifest["config"]["step_length"]
            neighbors = [n for n in state["neighbors"] if abs(n["gap"]) <= 20]
            self.weave_bus_neighbor_seconds += dt * any(n["type"] == "BUS" for n in neighbors)
            self.weave_car_neighbor_seconds += dt * any(n["type"] == "HV" for n in neighbors)
            self.weave_bus_leader_seconds += dt * any(n["type"] == "BUS" and n["lane_offset"] == 0 and n["leader"] for n in neighbors)
            self.weave_braking_seconds += dt * (acc < -.5)
        if self.trace:
            self.trace.write(json.dumps({"time": self.c.simulation.getTime(), "controller": self.controller,
                                         "schema": self.schema, "observation": self.last_obs.tolist(),
                                         "state": state, "action": action}) + "\n")

    def step(self, action):
        if self.done or self.c is None:
            raise RuntimeError("Call reset before step, and reset after episode termination")
        event = None
        previous = self.last_state
        if self.controller == "external":
            event = apply_safe_action(self.c, self.ego_id, action, previous, self.cfg,
                                      self.manifest["config"].get("no_lane_change_edges", []))
            self.requested_changes += int(event["lane_request_submitted"])
            if event["rejection"]:
                self.rejections[event["rejection"]] = self.rejections.get(event["rejection"], 0) + 1
        self._tick()
        collided = self.ego_id in self.collisions
        teleported = self.ego_id in self.teleports
        arrived = self.ego_id in self.arrived
        alive = self.ego_id in self.c.vehicle.getIDList()
        route_error = False
        changed = False
        if alive:
            self.last_obs, self.last_state = self.observer.observe()
            changed = (previous["edge"] == self.last_state["edge"] and previous["lane"] != self.last_state["lane"])
            self.actual_lane_changes += int(changed)
            self._record(event)
            route_error = self.last_state["route"] != self.expected_route or self.visited != self.expected_route[:len(self.visited)]
        timeout = self.c.simulation.getTime() >= self.cfg.get("time_limit", 600)
        if collided:
            self.status = "collision"
        elif teleported:
            self.status = "teleport"
        elif route_error:
            self.status = "route_deviation"
        elif arrived:
            self.status = "arrived" if self.visited == self.expected_route else "unexpected_destination"
        elif not alive:
            self.status = "unexpected_removal"
        elif timeout:
            self.status = "timeout"
        self.done = self.status != "running"
        lead = next((n for n in self.last_state.get("neighbors", []) if n["lane_offset"] == 0 and n["leader"]), None)
        gap = abs(lead["gap"]) if lead else None
        # Same reward concepts as the highway; local speed limit replaces 12km-road vmax.
        reward = .1 * self.last_state.get("speed", 0) / max(.1, self.c.vehicle.getAllowedSpeed(self.ego_id) if alive else 1)
        reward -= .1 if gap is not None and gap < 6 else 0
        reward -= .02 if event and event["rejection"] else 0
        if self.done:
            reward = 2. if self.status == "arrived" else -5.
        info = {**self.last_state, "status": self.status, "collided": collided,
                "arrived": self.status == "arrived", "gap": gap, "action": event,
                "lane_change": self.last_state.get("lane_index", 0) - previous.get("lane_index", 0) if changed else 0,
                "lane_change_applied": changed, "lane_before": previous.get("lane_index"),
                "lane_after": self.last_state.get("lane_index") if alive else None}
        if not alive:
            info["speed"] = None
        if self.done and self.trace:
            self.trace.write(json.dumps({"time": self.c.simulation.getTime(), "status": self.status,
                                         "action": event}) + "\n")
        return (self.last_obs.copy() if alive else np.zeros(self.obs_dim, dtype=np.float32),
                float(reward), self.done and self.status != "timeout", self.status == "timeout", info)

    def get_privileged_state(self):
        """Post-tick world snapshot, never an input to the behavior policy.

        Terminal snapshots retain the real world/time but use ego=None when
        SUMO has removed the AV. Do not reuse last_state's stale ego position.
        """
        if not self.collect_state or self.c is None:
            raise RuntimeError("Privileged snapshots require an active collect_state=True environment")
        values = self.c.vehicle.getAllSubscriptionResults()
        vehicles = []
        for vid, d in sorted(values.items()):
            route = list(d[tc.VAR_EDGES])
            vehicles.append({"id": vid, "type": d[tc.VAR_TYPE],
                "x": d[tc.VAR_POSITION][0], "y": d[tc.VAR_POSITION][1],
                "speed": d[tc.VAR_SPEED], "acceleration": d[tc.VAR_ACCELERATION],
                "allowed_speed": d[tc.VAR_ALLOWED_SPEED],
                "edge": d[tc.VAR_ROAD_ID], "lane": d[tc.VAR_LANE_ID],
                "lane_index": d[tc.VAR_LANE_INDEX], "lane_position": d[tc.VAR_LANEPOSITION],
                "length": d[tc.VAR_LENGTH], "route_id": d[tc.VAR_ROUTE_ID],
                "route": route, "route_index": d[tc.VAR_ROUTE_INDEX],
                "destination": route[-1] if route else None})
        ego = next((v for v in vehicles if v["id"] == self.ego_id), None)
        for v in vehicles:
            v["relative_xy"] = [v["x"] - ego["x"], v["y"] - ego["y"]] if ego else None
            v["distance_to_ego"] = math.hypot(*v["relative_xy"]) if ego else None
            v["relative_speed"] = v["speed"] - ego["speed"] if ego else None
        return {"time": self.c.simulation.getTime(), "ego_id": self.ego_id,
                "ego_alive": ego is not None, "ego": ego, "vehicles": vehicles,
                "expected_route": list(self.expected_route), "status": self.status}

    def get_detected_vehicles(self):
        """Cached nearest-neighbor detections from the SAME observation frame.

        Deduplicate vehicles seen in multiple lane/leader roles. Extra physical
        attributes are diagnostic annotations, not extra policy features.
        """
        if self.c is None or self.ego_id not in self.c.vehicle.getIDList():
            return []
        detected = {}
        for n in self.last_state.get("neighbors", []):
            item = detected.setdefault(n["id"], {"id": n["id"], "type": n["type"],
                "x": n["position_xy"][0], "y": n["position_xy"][1], "speed": n["speed"],
                "length": n["length"], "relative_speed": n["relative_speed"], "sightings": []})
            item["sightings"].append({k: n[k] for k in ("lane_offset", "leader", "gap", "bumper_gap", "longitudinal_overlap")})
        return [detected[k] for k in sorted(detected)]

    def finish(self, drain=True, hold_gui=False):
        if self.c is None:
            raise RuntimeError("No active simulation")
        if drain:
            while self.c.simulation.getMinExpectedNumber() and self.c.simulation.getTime() < self.cfg.get("time_limit", 600):
                self._tick()
        remaining = self.c.simulation.getMinExpectedNumber()
        end = self.c.simulation.getTime()
        if self.gui and hold_gui:
            input("Simulation finished. GUI stays open for inspection. Press Enter in CMD to close the connection and finalize logs: ")
        self.close()
        changes = [dict(e.attrib) for e in ET.parse(self.out / (self.name + ".lanechanges.xml")).findall("change")]
        ego_changes = [c for c in changes if c["id"] == self.ego_id]
        trips = [dict(e.attrib) for e in ET.parse(self.out / (self.name + ".trips.xml")).findall("tripinfo")]
        warnings = (self.out / (self.name + ".errors.log")).read_text(encoding="utf-8").splitlines()
        root = ET.parse(self.out / (self.name + ".rou.xml"))
        planned = len(root.findall("vehicle")) + sum(int(f.get("number")) for f in root.findall("flow"))
        result = {"controller": self.controller, "schema": self.schema, "obs_dim": self.obs_dim, "action_dim": 2,
                  "config": self.manifest["config"], "status": self.status, "route_id": self.route_id,
                  "origin": self.expected_route[0], "destination": self.expected_route[-1], "visited_edges": self.visited,
                  "av_arrived": self.status == "arrived", "av_lane_changes": ego_changes,
                  "av_weave_lane_changes": [c for c in ego_changes if c["from"].startswith("weave_") and c["to"].startswith("weave_")],
                  "av_min_acceleration": self.min_accel, "av_hard_braking_episodes": self.harsh,
                  "av_mean_speed_mps": self.speed_sum / self.steps if self.steps else None,
                  "av_weave_bus_neighbor_seconds": self.weave_bus_neighbor_seconds,
                  "av_weave_car_neighbor_seconds": self.weave_car_neighbor_seconds,
                  "av_weave_bus_leader_seconds": self.weave_bus_leader_seconds,
                  "av_weave_braking_seconds": self.weave_braking_seconds,
                  "av_weave_enter": self.weave_enter, "av_weave_exit": self.weave_exit,
                  "lane_requests_submitted": self.requested_changes, "rejected_actions": self.rejections,
                  "planned": planned, "departed": len(self.departed), "arrived": len(self.arrived),
                  "not_inserted": planned - len(self.departed), "remaining": remaining,
                  "simulation_end": end, "collisions": sorted(set(self.collisions)), "teleports": self.teleports,
                  "warnings": warnings, "trips": trips, "lane_changes": changes}
        (self.out / (self.name + ".result.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def close(self):
        if self.c is not None:
            self.c.close(wait=True)
            self.c = None
        for f in self.files:
            f.close()
        self.files = []

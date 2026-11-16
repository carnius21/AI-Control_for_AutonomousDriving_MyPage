"""MCW curriculum training and ablation runner for Toegyewon IC (47-dim ClarityEnv).

Supports:
  - Traffic stages: none (0x), low (0.2x ~3000 vph), high (1.0x 15000 vph),
    real_ratio (2025 observed vehicle-type mix: 77% car / 18% delivery / 4% truck / 1% bus)
  - Modular completion-rate levers:
      * --safety / --no-safety         : lane_change_safety gate
      * --route-conn / --no-route-conn : route-aware _lane_connectivity
      * --ttc-reward / --no-ttc-reward : longitudinal TTC & speed-proportional gap penalty
      * --prep-reward / --no-prep-reward : 300m-400m advance lane preparation reward
  - Curriculum resume (--resume path/to/model.pt)
  - 16-route evaluation (--eval-only)
"""
import argparse
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import torch

from algorithms.ppo import PPO
from env import ic_experiment as ic
from env.mdp_config import ACTION, OBSERVATION, REWARD as REWARD_DEFAULTS, SIMULATION
from env.navigation_clarity import ClarityEnv
from env.navigation_observation import RouteNavigation
from env.road_config import EGO, ROAD, TRAFFIC
from env.sumo_env import traci
from utils.buffer import RolloutBuffer
from utils.logger import RunLogger
from utils.train_lane_learning import ProgressReward

ROOT = Path(__file__).resolve().parents[1]
BASE_SCENARIO = ROOT / "scenarios" / "hv_high15000_entryprep"
ROUTES = [f"route_{i:02d}" for i in range(1, 17)]


def load_network_metadata(net_path: Path, rou_path: Path, nav_horizon: float = 400.0):
    """Parse network.net.xml and highway.rou.xml into ClarityEnv road & RouteNavigation."""
    net = ET.parse(str(net_path))
    edges = {e.get("id"): e for e in net.findall("edge") if not e.get("function")}
    paths = {
        e.get("id"): e.get("edges").split()
        for e in ET.parse(str(rou_path)).findall("route")
        if e.get("id", "").startswith("route_")
    }
    connections = [
        (c.get("from"), c.get("to"), int(c.get("fromLane")), int(c.get("toLane")))
        for c in net.findall("connection")
        if c.get("from") in edges and c.get("to") in edges
    ]
    lengths = {k: max(float(l.get("length")) for l in e.findall("lane")) for k, e in edges.items()}
    internal = {
        l.get("id"): float(l.get("length"))
        for e in net.findall("edge")
        if e.get("function") == "internal"
        for l in e.findall("lane")
    }
    links = {}
    for c in net.findall("connection"):
        key = (c.get("from"), c.get("to"))
        links[key] = max(links.get(key, 0.0), internal.get(c.get("via"), 0.0))

    counts = {k: len(e.findall("lane")) for k, e in edges.items()}
    nav = RouteNavigation(counts, connections, lengths, horizon=nav_horizon, link_lengths=links)
    solid_edges = [
        k for k, e in edges.items()
        if any(l.get("changeLeft") or l.get("changeRight") for l in e.findall("lane"))
    ]
    road = dict(
        ROAD,
        use_osm=True,
        routes=paths,
        edges=[(k, e.get("from"), e.get("to"), len(e.findall("lane"))) for k, e in edges.items()],
        connections=connections,
        solid_lane_edges=solid_edges,
    )
    ic.RAMPS = {k for k, e in edges.items() if e.get("type", "").endswith("_link")}
    ic.ZIP = ()
    return road, nav


def prepare_scenario(stage: str, cache_dir: Path) -> Path:
    """Create a scenario folder for stage ('none', 'low', 'high', 'real_ratio') and return run.sumocfg."""
    dest = cache_dir / stage
    dest.mkdir(parents=True, exist_ok=True)
    net_dst = dest / "network.net.xml"
    rou_dst = dest / "highway.rou.xml"
    cfg_dst = dest / "run.sumocfg"

    shutil.copy2(str(BASE_SCENARIO / "network.net.xml"), str(net_dst))
    shutil.copy2(str(BASE_SCENARIO / "run.sumocfg"), str(cfg_dst))

    tree = ET.parse(str(BASE_SCENARIO / "highway.rou.xml"))
    root = tree.getroot()

    if stage == "none":
        for flow in list(root.findall("flow")):
            root.remove(flow)
    elif stage == "low":
        for flow in root.findall("flow"):
            num = int(flow.get("number", "100"))
            flow.set("number", str(max(1, round(num * 0.2))))
    elif stage in ("real_ratio", "high_real_ratio"):
        # 2025 observed mix: Passenger 77%, Small Delivery 18%, Heavy Truck 4%, Bus 1%
        # Add delivery and truck vTypes and update carDist probabilities.
        deliv = ET.Element("vType", {
            "id": "delivery_idm", "vClass": "delivery", "guiShape": "delivery",
            "length": "5.5", "width": "2.0", "carFollowModel": "IDM",
            "accel": "1.6", "decel": "3.5", "emergencyDecel": "8",
            "tau": "1.3", "minGap": "2.2", "maxSpeed": "27.78", "speedDev": "0.1",
        })
        truck = ET.Element("vType", {
            "id": "truck_idm", "vClass": "truck", "guiShape": "truck",
            "length": "9.0", "width": "2.5", "carFollowModel": "IDM",
            "accel": "1.1", "decel": "3.2", "emergencyDecel": "7",
            "tau": "1.5", "minGap": "2.8", "maxSpeed": "25.0", "speedDev": "0.08",
        })
        dist = root.find("vTypeDistribution")
        if dist is not None:
            idx = list(root).index(dist)
            root.insert(idx, deliv)
            root.insert(idx + 1, truck)
            dist.set(
                "vTypes",
                "car_krauss car_idm car_eidm car_acc "
                "car_krauss_violator car_idm_violator car_eidm_violator car_acc_violator "
                "delivery_idm truck_idm bus_idm",
            )
            dist.set(
                "probabilities",
                "0.2641 0.2264 0.1509 0.1132 0.0054 0.0046 0.0031 0.0023 0.1800 0.0400 0.0100",
            )
        if stage == "real_ratio":
            for flow in root.findall("flow"):
                num = int(flow.get("number", "100"))
                flow.set("number", str(max(1, round(num * 0.5))))

    tree.write(str(rou_dst), encoding="utf-8", xml_declaration=True)
    return cfg_dst


class McwEnv(ClarityEnv):
    """ClarityEnv with route-aware connectivity, TTC safety reward, and 300-400m lane prep reward."""

    # Zipper merge foe lanes: ego_lane -> list of (foe_incoming_lane, foe_via_lane)
    MERGE_FOES = {
        "169728849_0": [("544295537_0", ":1808903166_1_0")],
        "544295537_0": [("169728849_0", ":1808903166_0_0")],
        "169929503#0_0": [("170059992_0", ":1810880137_0_0")],
        "170059992_0": [("169929503#0_0", ":1810880137_1_0")],
        "206426298#1_0": [("544292616_1", ":1000493465_0_1")],
        "544292616_1": [("206426298#1_0", ":1000493465_2_0")],
    }
    INTERNAL_MERGE_FOES = {
        ":1808903166_0_0": [":1808903166_1_0"],
        ":1808903166_1_0": [":1808903166_0_0"],
        ":1810880137_0_0": [":1810880137_1_0"],
        ":1810880137_1_0": [":1810880137_0_0"],
        ":1000493465_0_1": [":1000493465_2_0"],
        ":1000493465_2_0": [":1000493465_0_1"],
    }

    def __init__(self, *args, route_conn: bool = True, ttc_reward: bool = True,
                 prep_reward: bool = True, prep_horizon: float = 400.0,
                 timeout_penalty: float = 15.0, stall_penalty: float = 0.08, **kwargs):
        self.use_route_conn = route_conn
        self.use_ttc_reward = ttc_reward
        self.use_prep_reward = prep_reward
        self.prep_horizon = float(prep_horizon)
        self.timeout_penalty = float(timeout_penalty)
        self.stall_penalty = float(stall_penalty)
        self.credits = ProgressReward()
        super().__init__(*args, **kwargs)

    def reset(self, *args, **kwargs):
        self.credits = ProgressReward()
        return super().reset(*args, **kwargs)

    def _scan_lane_neighbors(self, direction: int):
        """Scan target lane AND across junction boundary (via + outgoing lanes) to prevent edge-end blind spots."""
        front, rear = super()._scan_lane_neighbors(direction)
        try:
            edge = traci.vehicle.getRoadID(self.ego_id)
            li = traci.vehicle.getLaneIndex(self.ego_id) + direction
            if edge.startswith(":") or li < 0 or li >= traci.edge.getLaneNumber(edge):
                return front, rear
            lane_id = f"{edge}_{li}"
            my_pos = traci.vehicle.getLanePosition(self.ego_id)
            remaining = traci.lane.getLength(lane_id) - my_pos
            if remaining < 35.0:
                for lk in traci.lane.getLinks(lane_id):
                    via_lane = lk[4] if len(lk) > 4 else ""
                    via_len = float(lk[7]) if len(lk) > 7 else 0.0
                    if via_lane:
                        for vid in traci.lane.getLastStepVehicleIDs(via_lane):
                            d = remaining + traci.vehicle.getLanePosition(vid)
                            g = d - traci.vehicle.getLength(vid)
                            if front is None or g < front[0]:
                                front = (g, traci.vehicle.getSpeed(vid))
                    next_lane = lk[0] if len(lk) > 0 else ""
                    if next_lane:
                        for vid in traci.lane.getLastStepVehicleIDs(next_lane):
                            vpos = traci.vehicle.getLanePosition(vid)
                            vlen = traci.vehicle.getLength(vid)
                            if vpos - vlen <= 5.0:
                                d = remaining + via_len + vpos
                                g = d - vlen
                                if front is None or g < front[0]:
                                    front = (g, traci.vehicle.getSpeed(vid))
        except traci.TraCIException:
            pass
        return front, rear

    def _neighbor(self, offset: int, leader: bool):
        """Fix zipper-merge foe blind spot on ego lane while keeping lateral observation distribution unchanged."""
        res = super()._neighbor(offset, leader)
        try:
            if offset == 0 and leader:
                edge = traci.vehicle.getRoadID(self.ego_id)
                li = traci.vehicle.getLaneIndex(self.ego_id)
                lane_id = f"{edge}_{li}"
                if edge.startswith(":"):
                    ifoes = self.INTERNAL_MERGE_FOES.get(lane_id)
                    if ifoes:
                        rem_ego = traci.lane.getLength(lane_id) - traci.vehicle.getLanePosition(self.ego_id)
                        for foe_via in ifoes:
                            foe_vlen = traci.lane.getLength(foe_via)
                            for vid in traci.lane.getLastStepVehicleIDs(foe_via):
                                rem_foe = foe_vlen - traci.vehicle.getLanePosition(vid)
                                if rem_foe <= rem_ego + 8.0:
                                    g = max(0.0, (rem_ego - rem_foe) - traci.vehicle.getLength(vid))
                                    v = float(traci.vehicle.getSpeed(vid))
                                    if res is None or g < res[0]:
                                        res = (g, v)
                else:
                    foes = self.MERGE_FOES.get(lane_id)
                    if foes:
                        rem_ego = traci.lane.getLength(lane_id) - traci.vehicle.getLanePosition(self.ego_id)
                        if rem_ego < self.visibility:
                            for foe_lane, foe_via in foes:
                                if foe_via:
                                    for vid in traci.lane.getLastStepVehicleIDs(foe_via):
                                        g = max(0.0, rem_ego + traci.vehicle.getLanePosition(vid) - traci.vehicle.getLength(vid))
                                        v = float(traci.vehicle.getSpeed(vid))
                                        if res is None or g < res[0]:
                                            res = (g, v)
                                foe_len = traci.lane.getLength(foe_lane)
                                for vid in traci.lane.getLastStepVehicleIDs(foe_lane):
                                    rem_foe = foe_len - traci.vehicle.getLanePosition(vid)
                                    # Foe vehicle arriving ahead of or right alongside ego at merge
                                    if rem_foe <= rem_ego + 8.0:
                                        g = max(0.0, rem_ego - max(0.0, rem_foe - 5.0))
                                        if g <= self.visibility:
                                            v = float(traci.vehicle.getSpeed(vid))
                                            if res is None or g < res[0]:
                                                res = (g, v)
        except traci.TraCIException:
            pass
        return res

    def _lane_connectivity(self, offset: int) -> float:
        if not self.use_route_conn:
            return super()._lane_connectivity(offset)
        try:
            edge = traci.vehicle.getRoadID(self.ego_id)
            if edge.startswith(":"):
                return 1.0
            lane_index = traci.vehicle.getLaneIndex(self.ego_id) + offset
            if lane_index < 0 or lane_index >= traci.edge.getLaneNumber(edge):
                return -1.0
            lane_id = f"{edge}_{lane_index}"
            remaining = traci.lane.getLength(lane_id) - traci.vehicle.getLanePosition(self.ego_id)
            if remaining > self.visibility:
                return 1.0

            # Check whether this lane actually connects to the next edge on ego's route
            path = self.routes.get(getattr(self, "episode_route", ""), [])
            idx = traci.vehicle.getRouteIndex(self.ego_id)
            if 0 <= idx and idx + 1 < len(path):
                next_edge = path[idx + 1]
                links = traci.lane.getLinks(lane_id)
                for lk in links:
                    if lk[0].startswith(next_edge + "_"):
                        return 1.0
                return float(np.clip(remaining / self.visibility, 0.0, 1.0))

            if traci.lane.getLinks(lane_id):
                return 1.0
            return float(np.clip(remaining / self.visibility, 0.0, 1.0))
        except traci.TraCIException:
            return 1.0

    def step(self, action):
        v_api = traci.vehicle
        alive_before = self.ego_id in v_api.getIDList()
        edge_before = v_api.getRoadID(self.ego_id) if alive_before else ""
        lane_before = v_api.getLaneIndex(self.ego_id) if alive_before else -1
        nav = self.navigation_context() if (alive_before and self.use_prep_reward) else None

        obs, reward, done, cut, info = super().step(action)

        extra = 0.0
        if cut and not done and self.timeout_penalty > 0.0:
            extra -= self.timeout_penalty
        if not done and self.ego_id in v_api.getIDList():
            ego_v = v_api.getSpeed(self.ego_id)
            lead = self._neighbor(0, leader=True)
            # 1) Longitudinal TTC & dynamic gap penalty
            if self.use_ttc_reward and lead is not None:
                gap, lead_v = lead
                dyn_safe = max(6.0, ego_v * 0.7)
                if gap < dyn_safe:
                    extra -= 0.08 * (1.0 - gap / dyn_safe)
                rel_closing = ego_v - lead_v
                if rel_closing > 0.5:
                    ttc = gap / rel_closing
                    if ttc < 2.5:
                        extra -= 0.15 * (1.0 - ttc / 2.5)
                        accel_raw = float(info.get("accel_raw", 0.0))
                        if accel_raw > 0.0:
                            extra -= 0.10 * accel_raw
            # 1b) Unobstructed low-speed / standstill penalty
            if self.stall_penalty > 0.0 and ego_v < 3.0:
                if lead is None or lead[0] > 25.0:
                    extra -= self.stall_penalty * (1.0 - ego_v / 3.0)

            # 2) Advance lane preparation reward (300-400m)
            if self.use_prep_reward and nav is not None:
                cur_edge = v_api.getRoadID(self.ego_id)
                if cur_edge == edge_before and not cur_edge.startswith(":"):
                    dist = nav.get("distance")
                    scaled = (dist * (100.0 / self.prep_horizon)) if dist is not None else None
                    extra += self.credits.award(
                        cur_edge, nav["prepare_targets"], lane_before,
                        v_api.getLaneIndex(self.ego_id), scaled,
                    )

        return obs, float(reward + extra), done, cut, info


def build_configs(args):
    action_cfg = dict(ACTION)
    action_cfg["lane_change_safety"] = dict(
        ACTION["lane_change_safety"],
        enabled=bool(args.safety),
        min_front_gap=float(args.min_front_gap),
        min_rear_gap=float(args.min_rear_gap),
        front_tau=0.3,
        rear_tau=float(args.rear_tau),
        approach_horizon=float(args.approach_horizon),
        spawn_protect=15.0,
    )
    reward_cfg = dict(
        REWARD_DEFAULTS,
        speed_weight=0.1,
        collision_penalty=args.collision_penalty,
        arrival_bonus=args.arrival_bonus,
        close_gap_threshold=6.0,
        close_gap_penalty=0.1,
        blocked_penalty=0.05,
        blocked_gap=20.0,
        blocked_speed_frac=0.7,
        lane_change_penalty=args.lc_penalty,
        invalid_action_penalty=0.0,
        ramp_speed_compliance=False,
        early_lane_guidance=False,
    )
    warmup = 5 if args.stage == "none" else (150 if args.smoke else 300)
    sim_cfg = dict(
        SIMULATION,
        step_length=0.2,
        max_steps=3000,   # 3000 * 0.2s = 600s max per episode
        warmup_steps=warmup,
    )
    ego_cfg = dict(EGO, max_speed=27.78, depart_lane="best", depart_speed="max")
    traffic_cfg = dict(TRAFFIC, prefill={"enabled": False})
    return action_cfg, reward_cfg, sim_cfg, ego_cfg, traffic_cfg


def make_env(cfg_path, road, nav, args, action_cfg, reward_cfg, sim_cfg, ego_cfg, traffic_cfg):
    return McwEnv(
        str(cfg_path), road, ego_cfg, sim_cfg, OBSERVATION, action_cfg, reward_cfg,
        traffic_cfg, (), args.seed,
        navigation=nav, clarity="lookahead",
        route_conn=args.route_conn, ttc_reward=args.ttc_reward,
        prep_reward=args.prep_reward, prep_horizon=args.nav_horizon,
        timeout_penalty=args.timeout_penalty, stall_penalty=args.stall_penalty,
    )


def evaluate_16_routes(agent, env, episodes_per_route: int = 1, base_seed: int = 40001):
    rows = []
    for r_idx, route in enumerate(ROUTES):
        for ep in range(episodes_per_route):
            s = base_seed + ep * 100 + r_idx
            try:
                obs, _ = env.reset(seed=s, options={"route": route})
            except RuntimeError as exc:
                rows.append({"route": route, "seed": s, "outcome": "insertion_failure", "error": str(exc)})
                continue
            speeds = []
            while True:
                act = agent.predict(obs, deterministic=True)
                obs, _, done, cut, info = env.step(act)
                if info.get("speed") is not None:
                    speeds.append(float(info["speed"]))
                if done or cut:
                    outcome = (
                        "collision" if info.get("collided")
                        else "arrival" if info.get("arrived")
                        else "timeout" if cut else "other"
                    )
                    rows.append({
                        "route": route,
                        "seed": s,
                        "outcome": outcome,
                        "steps": int(env.step_count),
                        "mean_speed": float(np.mean(speeds)) if speeds else 0.0,
                    })
                    break
    total = max(len(rows), 1)
    arr = sum(1 for x in rows if x["outcome"] == "arrival")
    col = sum(1 for x in rows if x["outcome"] == "collision")
    tmo = sum(1 for x in rows if x["outcome"] == "timeout")
    ins = sum(1 for x in rows if x["outcome"] == "insertion_failure")
    summary = {
        "total": len(rows),
        "arrivals": arr,
        "collisions": col,
        "timeouts": tmo,
        "insertion_failures": ins,
        "success_rate": arr / total,
        "collision_rate": col / total,
        "rows": rows,
    }
    return summary


def main():
    p = argparse.ArgumentParser(description="MCW Toegyewon IC curriculum trainer & evaluator")
    p.add_argument("--stage", choices=["none", "low", "high", "real_ratio", "high_real_ratio"], default="low")
    p.add_argument("--steps", type=int, default=200000)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--lane-entropy", type=float, default=0.002)
    p.add_argument("--lane-keep-bias", type=float, default=1.0)
    p.add_argument("--collision-penalty", type=float, default=15.0)
    p.add_argument("--timeout-penalty", type=float, default=15.0)
    p.add_argument("--stall-penalty", type=float, default=0.08)
    p.add_argument("--arrival-bonus", type=float, default=5.0)
    p.add_argument("--lc-penalty", type=float, default=0.02)
    p.add_argument("--nav-horizon", type=float, default=400.0)
    p.add_argument("--safety", dest="safety", action="store_true", default=True)
    p.add_argument("--no-safety", dest="safety", action="store_false")
    p.add_argument("--min-front-gap", type=float, default=5.0)
    p.add_argument("--min-rear-gap", type=float, default=5.0)
    p.add_argument("--rear-tau", type=float, default=0.5)
    p.add_argument("--approach-horizon", type=float, default=1.2)
    p.add_argument("--route-conn", dest="route_conn", action="store_true", default=True)
    p.add_argument("--no-route-conn", dest="route_conn", action="store_false")
    p.add_argument("--ttc-reward", dest="ttc_reward", action="store_true", default=True)
    p.add_argument("--no-ttc-reward", dest="ttc_reward", action="store_false")
    p.add_argument("--prep-reward", dest="prep_reward", action="store_true", default=True)
    p.add_argument("--no-prep-reward", dest="prep_reward", action="store_false")
    p.add_argument("--resume", type=str, default=None, help="Path to checkpoint .pt to resume from")
    p.add_argument("--eval-only", action="store_true")
    p.add_argument("--eval-episodes", type=int, default=1, help="Episodes per route (16 routes total)")
    p.add_argument("--eval-interval", type=int, default=25, help="Updates between 16-route evaluations (0=off)")
    p.add_argument("--name", type=str, default=None)
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    cache_dir = ROOT / "results" / "mcw_scenarios"
    cfg_path = prepare_scenario(args.stage, cache_dir)
    road, nav = load_network_metadata(cfg_path.parent / "network.net.xml", cfg_path.parent / "highway.rou.xml", args.nav_horizon)
    action_cfg, reward_cfg, sim_cfg, ego_cfg, traffic_cfg = build_configs(args)

    run_name = args.name or f"mcw_{args.stage}_s{args.seed}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "results" / "mcw_runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    hparams = dict(
        lr=args.lr,
        n_steps=1024 if args.smoke else 2048,
        n_epochs=10,
        minibatch_size=64,
        gamma=0.99,
        gae_lambda=0.95,
        clip_eps=0.2,
        value_coef=0.5,
        entropy_coef=0.0,
        lane_entropy_coef=args.lane_entropy,
        max_grad_norm=0.5,
        normalize_advantage=True,
        hidden_sizes=(256, 256),
        activation="tanh",
        policy_type="hybrid",
        lane_keep_bias=args.lane_keep_bias,
        init_log_std=-0.5,
        seed=args.seed,
        device="auto",
    )

    env = make_env(cfg_path, road, nav, args, action_cfg, reward_cfg, sim_cfg, ego_cfg, traffic_cfg)
    agent = PPO(obs_dim=47, act_dim=2, buffer=RolloutBuffer(), **hparams)
    if args.resume:
        agent.load(args.resume)
        print(f"[mcw_train] Resumed weights from: {args.resume}", flush=True)

    manifest = {
        "args": vars(args),
        "hparams": hparams,
        "action": action_cfg,
        "reward": reward_cfg,
        "device": str(agent.device),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        if args.eval_only:
            summary = evaluate_16_routes(agent, env, episodes_per_route=args.eval_episodes)
            (run_dir / "eval_16routes.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                f"[EVAL {args.stage}] arrival={summary['arrivals']}/{summary['total']} "
                f"({summary['success_rate']:.1%}), collision={summary['collisions']} "
                f"({summary['collision_rate']:.1%}), timeout={summary['timeouts']}",
                flush=True,
            )
            return

        logger = RunLogger(str(run_dir))
        try:
            obs, _ = env.reset()
            ep_stats = [0.0, 0]
            best_sr = -1.0
            n_updates = 0
            while agent.num_timesteps < args.steps:
                obs, last_val, _ = agent.collect_rollout(env, obs, logger=logger, ep_stats=ep_stats)
                adv, ret = agent.buffer.compute_gae(last_val, agent.gamma, agent.gae_lambda)
                stats = agent.update(adv, ret)
                n_updates += 1
                logger.log_train(agent.num_timesteps, {
                    "update": n_updates,
                    "ep_rew_mean": float("nan"),
                    "std": agent.policy.current_std,
                    **stats,
                }, verbose=True)

                if args.eval_interval > 0 and n_updates % args.eval_interval == 0:
                    summary = evaluate_16_routes(agent, env, episodes_per_route=args.eval_episodes)
                    (run_dir / f"eval_{agent.num_timesteps}.json").write_text(
                        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    logger.log_eval(agent.num_timesteps, {
                        "success_rate": summary["success_rate"],
                        "collision_rate": summary["collision_rate"],
                        "timeouts": summary["timeouts"],
                    })
                    print(
                        f"[EVAL @{agent.num_timesteps}] arrival={summary['arrivals']}/{summary['total']} "
                        f"({summary['success_rate']:.1%}), collision={summary['collisions']} "
                        f"({summary['collision_rate']:.1%}), timeout={summary['timeouts']}",
                        flush=True,
                    )
                    if summary["success_rate"] >= best_sr:
                        best_sr = summary["success_rate"]
                        agent.save(str(run_dir / "best_model.pt"))
                    obs, _ = env.reset()
                    ep_stats = [0.0, 0]
        finally:
            logger.close()
            agent.save(str(run_dir / "model.pt"))
            # Final 16-route evaluation
            summary = evaluate_16_routes(agent, env, episodes_per_route=args.eval_episodes)
            (run_dir / "eval_final.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                f"[FINAL EVAL {args.stage}] arrival={summary['arrivals']}/{summary['total']} "
                f"({summary['success_rate']:.1%}), collision={summary['collisions']} "
                f"({summary['collision_rate']:.1%}), timeout={summary['timeouts']}",
                flush=True,
            )
    finally:
        env.close()


if __name__ == "__main__":
    main()

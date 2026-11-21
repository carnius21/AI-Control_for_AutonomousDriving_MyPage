"""Matched navigation ablation. Run one process per condition using python -m."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import zipfile

os.environ["IC_LIBSUMO"] = "1"
import numpy as np
import torch
from utils import mcw_train as m
from env.sumo_env import traci
from env import ic_experiment as ic

OUT = m.ROOT / "results" / "jys2_nav_av_20261119"
WEIGHT = "results/mcw_runs/stage3_high_v5_b/best_model.pt"


class GuidanceEnv(m.McwEnv):
    def _get_obs(self):
        obs = super()._get_obs()
        if self.mode == "custom":
            return obs
        obs[31:34] = 0
        obs[37:] = 0
        if self.mode == "none" or self.ego_id not in traci.vehicle.getIDList():
            return obs
        v = traci.vehicle
        edge = v.getRoadID(self.ego_id)
        if edge.startswith(":"):
            return obs
        path = v.getRoute(self.ego_id)
        index = v.getRouteIndex(self.ego_id)
        remaining = traci.lane.getLength(v.getLaneID(self.ego_id)) - v.getLanePosition(self.ego_id)
        for j in range(index, len(path)-1):
            if remaining > self.navigation.horizon:
                break
            src, dst = path[j:j+2]
            exits = self.links[src]
            if len(exits) > 1:
                if src not in ic.RAMPS and any(x in ic.RAMPS for x in exits) and any(x not in ic.RAMPS for x in exits):
                    obs[31] = 1 if dst in ic.RAMPS else -1
                break
            remaining += self.navigation.link_lengths.get((src,dst),0) + self.navigation.lengths[dst]
        return obs


def evaluate(agent, env):
    rows = []
    for index, route in enumerate(m.ROUTES):
        for rep in range(3):
            seed = 41001 + index + rep * 100
            obs, _ = env.reset(seed=seed, options={"route": route})
            path = env.routes[route]
            previous = None
            missed = []
            last = None
            while True:
                v = traci.vehicle
                edge = v.getRoadID(env.ego_id)
                if not edge.startswith(":"):
                    if previous and previous[0] != edge:
                        src, expected = previous
                        if len(env.links[src]) > 1 and expected and expected != edge:
                            missed.append([src, expected, edge])
                    idx = v.getRouteIndex(env.ego_id)
                    nxt = path[idx+1] if 0 <= idx < len(path)-1 and path[idx] == edge else None
                    previous = edge, nxt
                    lane = v.getLaneIndex(env.ego_id)
                    last = dict(edge=edge, next=nxt, lane=lane,
                                remaining=round(traci.lane.getLength(v.getLaneID(env.ego_id))-v.getLanePosition(env.ego_id),2),
                                incompatible=bool(nxt and len(env.links[edge])>1 and lane not in env.links[edge][nxt]))
                obs, _, done, cut, info = env.step(agent.predict(obs, deterministic=True))
                if done or cut:
                    outcome = "collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                    rows.append(dict(route=route, seed=seed, outcome=outcome, missed=missed,last=last,
                                     wrong_lane_at_timeout=bool(cut and not done and not edge.startswith(":") and last["incompatible"] and last["remaining"] <= 10)))
                    break
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["none","sumo","custom"])
    mode = p.parse_args().mode
    torch.set_num_threads(1)
    folder = OUT / mode
    folder.mkdir(parents=True, exist_ok=True)
    cfg = m.prepare_scenario("high_real_ratio", folder)
    road, nav = m.load_network_metadata(cfg.parent / "network.net.xml",cfg.parent / "highway.rou.xml")
    archive = m.ROOT / "results/mcw_runs/mcw-models-20261116.zip"
    with zipfile.ZipFile(archive) as z:
        baseline = json.loads(z.read("results/mcw_runs/stage3_high_v5_b/manifest.json"))
        weights = z.read(WEIGHT)
    args = argparse.Namespace(**baseline["args"])
    args.stage, args.safety, args.prep_reward, args.smoke = "high_real_ratio", False, False, False
    args.approach_horizon = 1.2
    args.seed = 11
    action, reward, sim, ego, traffic = m.build_configs(args)
    ego["depart_lane"] = "0"
    env = GuidanceEnv(str(cfg), road, ego, sim, m.OBSERVATION, action, reward, traffic, (), args.seed,
                      navigation=nav, clarity="lookahead", route_conn=(mode=="custom"), prep_reward=False,
                      ttc_reward=args.ttc_reward, timeout_penalty=args.timeout_penalty, stall_penalty=args.stall_penalty)
    env.mode = mode
    hparams = dict(baseline["hparams"], seed=11, device="cpu",n_steps=2048)
    agent = m.PPO(obs_dim=47,act_dim=2,buffer=m.RolloutBuffer(),**hparams)
    initial = folder / "initial.pt"
    initial.write_bytes(weights)
    agent.load(str(initial))
    (folder/"settings.json").write_text(json.dumps(dict(mode=mode, seed=11, budget=51200,hparams=hparams, action=action,reward=reward,
                                 args=vars(args), route_connectivity=env.use_route_conn, ego=ego,sha256=hashlib.sha256(weights).hexdigest()),indent=2))
    try:
        obs,_ = env.reset()
        ep = [0.,0]
        while agent.num_timesteps < 51200:
            obs, last, _ = agent.collect_rollout(env, obs, ep_stats=ep)
            adv, ret = agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
            agent.update(adv,ret)
            print(mode, agent.num_timesteps, flush=True)
        agent.save(str(folder/"final.pt"))
        rows = evaluate(agent, env)
        (folder/"evaluation.json").write_text(json.dumps(rows,indent=2))
        print(Counter(r["outcome"] for r in rows), flush=True)
    finally:
        env.close()


if __name__ == "__main__":
    main()


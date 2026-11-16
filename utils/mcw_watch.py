"""Watch a trained MCW checkpoint in SUMO-GUI for any route & seed."""
import argparse
import traci

from algorithms.ppo import PPO, RolloutBuffer
from utils.mcw_train import (
    ROOT, McwEnv, prepare_scenario, load_network_metadata, build_configs,
)
from env.mdp_config import OBSERVATION


def main():
    p = argparse.ArgumentParser(description="Replay an episode in SUMO-GUI tracking ego")
    p.add_argument("--route", type=str, default="route_01", help="route_01 .. route_16")
    p.add_argument("--seed", type=int, default=40201)
    p.add_argument("--stage", choices=["none", "low", "high", "real_ratio"], default="high")
    p.add_argument("--resume", type=str, default="results/mcw_runs/stage3_high_v5_b/best_model.pt")
    p.add_argument("--delay", type=float, default=120.0, help="SUMO-GUI delay in ms per step")
    p.add_argument("--zoom", type=float, default=1200.0, help="SUMO-GUI camera zoom")
    p.add_argument("--min-front-gap", type=float, default=3.5)
    p.add_argument("--min-rear-gap", type=float, default=3.5)
    p.add_argument("--rear-tau", type=float, default=0.35)
    p.add_argument("--approach-horizon", type=float, default=1.2)
    args = p.parse_args()

    # Fill defaults expected by build_configs
    args.safety = True
    args.collision_penalty = 15.0
    args.arrival_bonus = 5.0
    args.lc_penalty = 0.01
    args.smoke = False
    args.nav_horizon = 400.0
    args.route_conn = True
    args.ttc_reward = True
    args.prep_reward = True
    args.timeout_penalty = 15.0
    args.stall_penalty = 0.08
    args.lane_entropy = 0.002
    args.lane_keep_bias = 0.5

    cfg_path = prepare_scenario(args.stage, ROOT / "results" / "mcw_scenarios")
    road, nav = load_network_metadata(
        cfg_path.parent / "network.net.xml",
        cfg_path.parent / "highway.rou.xml",
        args.nav_horizon,
    )
    action_cfg, reward_cfg, sim_cfg, ego_cfg, traffic_cfg = build_configs(args)
    sim_cfg["gui_delay"] = float(args.delay)
    sim_cfg["gui_zoom"] = float(args.zoom)
    sim_cfg["gui_track_ego"] = True

    env = McwEnv(
        str(cfg_path), road, ego_cfg, sim_cfg, OBSERVATION, action_cfg, reward_cfg,
        traffic_cfg, (), args.seed,
        navigation=nav, clarity="lookahead",
        route_conn=True, ttc_reward=True, prep_reward=True, prep_horizon=args.nav_horizon,
        timeout_penalty=args.timeout_penalty, stall_penalty=args.stall_penalty,
    )
    env.gui = True
    env.gui_autostart = True
    agent = PPO(
        obs_dim=47, act_dim=2, buffer=RolloutBuffer(),
        lr=1e-5, n_steps=2048, n_epochs=10, minibatch_size=64,
        gamma=0.99, gae_lambda=0.95, clip_eps=0.2, value_coef=0.5,
        entropy_coef=0.0, lane_entropy_coef=0.002, max_grad_norm=0.5,
        normalize_advantage=True, hidden_sizes=(256, 256), activation="tanh",
        policy_type="hybrid", lane_keep_bias=0.5, init_log_std=-0.5,
        seed=args.seed, device="auto",
    )
    agent.load(args.resume)

    try:
        cur_seed = args.seed
        while True:
            obs, _ = env.reset(seed=cur_seed, options={"route": args.route})
            print(f"Watching {args.route} (seed={cur_seed}) with {args.resume}")
            while True:
                act = agent.predict(obs, deterministic=True)
                obs, _, done, cut, info = env.step(act)
                if env.ego_id in traci.vehicle.getIDList():
                    edge = traci.vehicle.getRoadID(env.ego_id)
                    lane = traci.vehicle.getLaneIndex(env.ego_id)
                    v = traci.vehicle.getSpeed(env.ego_id)
                    print(
                        f"step={env.step_count:4d} edge={edge:<15s} lane={lane} "
                        f"v={v:5.2f} acc={info.get('accel_raw', 0.0):+5.2f} "
                        f"lc={info.get('lane_change', 0):+d}(ok={info.get('lane_change_applied', False)})",
                        flush=True,
                    )
                if done or cut:
                    outcome = (
                        "collision" if info.get("collided")
                        else "arrival" if info.get("arrived")
                        else "timeout"
                    )
                    print(f"=== FINISHED: {outcome} at step {env.step_count} ===")
                    break
            ans = input("[r] 같은 장면 다시 보기 / [n] 다음 시드(+100) / [Enter] 종료: ").strip().lower()
            if ans == "r":
                continue
            elif ans == "n":
                cur_seed += 100
                continue
            else:
                break
    finally:
        env.close()


if __name__ == "__main__":
    main()

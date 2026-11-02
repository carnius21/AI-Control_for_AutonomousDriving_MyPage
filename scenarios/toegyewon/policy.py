"""Strict, inference-only adapter for the repository's PPO checkpoints."""

from pathlib import Path


def load_ppo(path, obs_dim, schema, activation="relu"):
    import torch
    from algorithms.ppo import PPO

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"PPO checkpoint not found: {path}. Use --av sumo for the baseline.")
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Expected a PPO state_dict or PPO metadata wrapper")
    wrapped = "state_dict" in checkpoint
    if wrapped and checkpoint.get("algorithm") != "ppo":
        raise ValueError("Only PPO checkpoints are supported by this adapter")
    state = checkpoint["state_dict"] if wrapped else checkpoint
    if "trunk.0.weight" not in state or "mu_head.weight" not in state:
        raise ValueError("Not a supported repository PPO checkpoint")
    found_dim = int(state["trunk.0.weight"].shape[1])
    if found_dim != obs_dim:
        raise ValueError(f"PPO input dimension {found_dim} != environment {obs_dim}. "
                         "31-input highway policies require explicit --observation legacy; "
                         "route43 requires a separately trained policy. No padding/truncation is performed.")
    if wrapped and checkpoint.get("observation_schema") != schema:
        raise ValueError(f"Checkpoint observation schema must equal {schema}")
    kind = "hybrid" if "lane_head.weight" in state else "gaussian"
    if (kind == "hybrid" and (state["mu_head.weight"].shape[0] != 1 or state["lane_head.weight"].shape[0] != 3)
            or kind == "gaussian" and state["mu_head.weight"].shape[0] != 2):
        raise ValueError("PPO output must represent acceleration plus lane change (2 actions)")
    hidden = tuple(int(v.shape[0]) for k, v in sorted(state.items(), key=lambda kv: int(kv[0].split('.')[1]) if kv[0].startswith('trunk.') else -1)
                   if k.startswith("trunk.") and k.endswith(".weight"))
    selected_activation = checkpoint.get("activation", activation) if wrapped else activation
    if selected_activation not in ("relu", "tanh", "elu"):
        raise ValueError("Unsupported PPO activation")
    agent = PPO(obs_dim=obs_dim, act_dim=2, hidden_sizes=hidden, activation=selected_activation,
                policy_type=kind, device="cpu")
    try:
        agent.policy.load_state_dict(state, strict=True)
    except RuntimeError as exc:
        raise ValueError("PPO architecture mismatch") from exc
    agent.policy.eval()
    agent.checkpoint_info = {"path": str(path.resolve()), "input_dim": found_dim, "action_dim": 2,
                             "policy_type": kind, "hidden_sizes": hidden, "activation": selected_activation,
                             "schema_verified": wrapped,
                             "note": "Bare highway checkpoints have no observation/activation metadata; dimension compatibility is not policy validity." if not wrapped else None}
    return agent


def run_av(out, manifest, gui=False, checkpoint=None):
    from .av_env import ToegyewonEnv

    cfg = manifest["config"]["av"]
    mode = cfg.get("controller", "sumo")
    if mode not in ("sumo", "ppo"):
        raise ValueError("CLI AV controller must be sumo or ppo; external actions use ToegyewonEnv directly")
    env = ToegyewonEnv(out, manifest, "sumo" if mode == "sumo" else "external", name="av_" + mode, gui=gui)
    agent = None
    if mode == "ppo":
        if not checkpoint:
            raise ValueError("--av ppo requires --checkpoint. No trained checkpoint is bundled; use --av sumo.")
        agent = load_ppo(checkpoint, env.obs_dim, env.schema, cfg.get("policy_activation", "relu"))
    try:
        obs, _ = env.reset()
        while not env.done:
            action = agent.predict(obs, deterministic=True) if agent else None
            obs, _, _, _, _ = env.step(action)
        result = env.finish(hold_gui=gui)
    finally:
        env.close()
    import json
    result["control_description"] = "SUMO baseline (not learned)" if mode == "sumo" else "PPO proposals with SUMO safety and route guard"
    result["checkpoint"] = agent.checkpoint_info if agent else None
    Path(out, "av_" + mode + ".result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("control_description", "status", "origin", "destination", "av_mean_speed_mps", "av_min_acceleration", "collisions", "teleports", "remaining")}, indent=2))
    if not result["av_arrived"] or result["collisions"] or result["teleports"] or result["warnings"] or result["remaining"]:
        raise RuntimeError(f"AV scenario failed: {result['status']}; inspect av_{mode}.result.json")
    return result

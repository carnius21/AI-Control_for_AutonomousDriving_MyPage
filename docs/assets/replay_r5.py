"""Replay route 13 from the team's R5 evaluation. Run in the jys3 project root."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="Run without the SUMO window")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if not (root / "results/jys3_final_relu_dagger/dagger5.pt").is_file():
        parser.exit(2, "Place replay_r5.py next to requirements.txt in the extracted jys3 folder.\n")
    os.chdir(root)

    import sumo
    import torch

    # Training helpers default to libsumo. Select the GUI-capable TraCI backend first.
    os.environ["SUMO_HOME"] = str(sumo.SUMO_HOME)
    os.environ["IC_LIBSUMO"] = "0"
    from env.sumo_env import traci
    from utils.jys3_final_relu_dagger import checkpoint, network
    from utils.jys3_train_physical_imitation import simulator

    torch.set_num_threads(1)
    policy = network(checkpoint(5))
    with simulator() as env, torch.inference_mode():
        env.sim.gui = not args.headless
        env.sim.gui_autostart = True
        env.sim.gui_delay = 35
        env.ego_depart_lane = "0"
        obs, _ = env.reset(seed=104320013, options={"route": "route_13"})
        if env.sim.gui:
            traci.vehicle.setColor(env.ego_id, (255, 0, 0, 255))
        steps = 0
        while True:
            state = torch.from_numpy(obs[:50]).unsqueeze(0)
            action = policy.det_action(state)[0].numpy()
            obs, _, done, truncated, info = env.step(action)
            steps += 1
            if done or truncated:
                print(f"route_13 | {info['outcome']} | {steps} steps")
                break


if __name__ == "__main__":
    main()

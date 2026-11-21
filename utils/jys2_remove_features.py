"""Frozen-policy ablations of the 47-dimensional jys2 checkpoint."""
import argparse
import json
from pathlib import Path

from utils.jys2_nav_av import OUT, m, torch
from env.sumo_env import traci

MASKS = {"next_lane": [31], "prep_distance": [32], "prep_direction": [33],
         "validity": [37, 38], "second_split": list(range(39,47))}
FEATURES = {*MASKS, "route_conn", "gate"}
DEST = OUT / "removals"


class AblationEnv(m.McwEnv):
    def _get_obs(self):
        obs = super()._get_obs()
        for key in self.removed:
            if key in MASKS:
                obs[MASKS[key]] = 0.
        return obs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("condition", choices=["all","baseline",*sorted(FEATURES)])
    parser.add_argument("--depart-lane", choices=["best","0"], default="best")
    options = parser.parse_args()
    cond = options.condition
    removed = FEATURES if cond == "all" else set() if cond == "baseline" else {cond}
    torch.set_num_threads(1)
    source = OUT/"custom"
    s=json.loads((source/"settings.json").read_text())
    a=argparse.Namespace(**s["args"])
    a.safety="gate" not in removed
    act,rw,sim,ego,traffic=m.build_configs(a)
    ego["depart_lane"]=options.depart_lane
    cfg=source/"high_real_ratio"/"run.sumocfg"
    road,nav=m.load_network_metadata(cfg.parent/"network.net.xml",cfg.parent/"highway.rou.xml")
    env=AblationEnv(str(cfg),road,ego,sim,m.OBSERVATION,act,rw,traffic,(),11,
        navigation=nav,clarity="lookahead",route_conn="route_conn" not in removed,
        prep_reward=False,ttc_reward=a.ttc_reward,timeout_penalty=a.timeout_penalty,stall_penalty=a.stall_penalty)
    env.removed=removed
    label = cond if options.depart_lane=="best" else f"{cond}_lane0"
    agent=m.PPO(obs_dim=47,act_dim=2,buffer=m.RolloutBuffer(),**s["hparams"])
    agent.load(str(source/"initial.pt"))
    try:
        result=m.evaluate_16_routes(agent,env,episodes_per_route=3,base_seed=41001)
        assert len(result["rows"])==48 and sum(result[k] for k in ("arrivals","collisions","timeouts"))==48
        result["removed"]=sorted(removed)
        (DEST/f"{label}.json").write_text(json.dumps(result,indent=2))
        print(cond,result["arrivals"],result["collisions"],result["timeouts"],flush=True)
    finally:
        env.close()


if __name__=="__main__":
    DEST.mkdir(parents=True,exist_ok=True)
    main()


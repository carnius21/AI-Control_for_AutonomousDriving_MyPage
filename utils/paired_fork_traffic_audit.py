"""Unconditional paired high-traffic evaluation with event details."""
from concurrent.futures import ProcessPoolExecutor
from utils.paired_fork_pilot import OUT, ROOT, ARM, TEST, evaluate, make, m, save, torch
import sys

def audit(args):
    seed,steps=args
    folder=OUT/str(seed)
    torch.set_num_threads(1)
    agent=m.PPO(obs_dim=40,act_dim=2,buffer=m.RolloutBuffer(),seed=seed,device="cpu",hidden_sizes=(256,256))
    weight=(folder/f"policy_plus_{steps}.pt" if steps else ROOT/f"{ARM}_{seed}"/"policy_650000.pt")
    agent.load(str(weight))
    env=make("high_real_ratio",ARM,seed,folder/"traffic_audit")
    env.record=True
    env.ego_depart_lane="1"
    try: save(folder/f"traffic_audit_{steps}.json",evaluate(env,agent,TEST))
    finally: env.close()

if __name__=="__main__":
    with ProcessPoolExecutor(3) as pool:
        list(pool.map(audit,[(seed,int(sys.argv[1])) for seed in (11,22,33)]))

"""Experiment A training worker and paired checkpoint evaluation."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import subprocess
import sys
from utils.experiment_a import ROOT, STAGES, SIZE, CONTINUATIONS, OBS_TRIALS, VALIDITY_TRIALS, make, m, torch


def save(path,data):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2))
    tmp.replace(path)


def worker(arm,seed,eval_step=0,holdout=False):
    torch.set_num_threads(1)
    folder=ROOT/f"{arm}_{seed}"
    folder.mkdir(parents=True,exist_ok=True)
    agent=m.PPO(obs_dim=SIZE,act_dim=2,buffer=m.RolloutBuffer(),seed=seed,device="cpu",
                hidden_sizes=(256,256),n_steps=2048,n_epochs=10,minibatch_size=64,
                lr=.0001,lane_entropy_coef=.002,lane_keep_bias=1.)
    if arm in VALIDITY_TRIALS:
        # Preserve optimizer parameter references and the original PPO sampling RNG.
        layer = agent.policy.trunk[0]
        with torch.no_grad():
            layer.weight.data = torch.nn.functional.pad(layer.weight.data, (0, 2))
        layer.in_features += 2
    if eval_step:
        from utils.failure_log import FailureLog
        agent.load(str(folder/f"policy_{eval_step}.pt"))
        final=eval_step==(650000 if arm in CONTINUATIONS else 600000)
        stage="high_real_ratio" if final or holdout or arm in CONTINUATIONS else STAGES[(eval_step-1)//200000]
        env=make(stage,arm,seed,folder/"eval_maps")
        env.record=final or holdout
        name=("holdout_" if holdout else "eval_")+str(eval_step)
        rows=[]
        try:
            with gzip.open(folder/f"{name}_trace.jsonl.gz","wt") as trace:
                for i,r in enumerate(m.ROUTES):
                    for n in range(3 if final or holdout else 1):
                        s=(73001 if holdout else 41001 if final else 63001)+i+100*n
                        obs,_=env.reset(seed=s,options={"route":r})
                        env.last_wrong=False
                        failures=FailureLog()
                        while True:
                            failures.before(env,obs)
                            obs,_,done,cut,info=env.step(agent.predict(obs,deterministic=True))
                            if not (done or cut):
                                failures.after(env,info)
                            if done or cut:
                                outcome="collision" if info["collided"] else "arrival" if info["arrived"] else "timeout" if cut else "other"
                                rows.append(dict(route=r,seed=s,outcome=outcome,wrong_timeout=bool(cut and env.last_wrong),metrics=env.events,failure=failures.after(env,info,outcome)))
                                if env.record:
                                    trace.write(json.dumps([r,s,env.trace])+"\n")
                                break
            save(folder/f"{name}.json",rows)
        finally:
            env.close()
        return
    restart = arm in ("A0_prep_only","A0_restart_control",*OBS_TRIALS)
    if arm in CONTINUATIONS:
        agent.load(str(ROOT/f"prep_both_{seed}"/"policy_600000.pt"))
        agent.num_timesteps = 600000
    elif restart:
        parent = ROOT/f"A0_no_lc_cost_{seed}"/"policy_400000.pt"
        if arm in VALIDITY_TRIALS:
            state = torch.load(parent, map_location="cpu", weights_only=True)
            state["trunk.0.weight"] = torch.nn.functional.pad(state["trunk.0.weight"], (0, 2))
            agent.policy.load_state_dict(state)
        else:
            agent.load(str(parent))
        agent.num_timesteps = 400000
    for i,stage in enumerate(STAGES):
        if restart and i < 2:
            continue
        end=650000 if arm in CONTINUATIONS else (i+1)*200000
        interval=25000 if arm in CONTINUATIONS else 50000
        env=make(stage,arm,seed,folder/"maps")
        try:
            obs,_=env.reset()
            episode_stats=[0.,0]
            while agent.num_timesteps<end:
                target=min(end,(agent.num_timesteps//interval+1)*interval)
                steps=min(2048,target-agent.num_timesteps)
                obs,last,_=agent.collect_rollout(env,obs,ep_stats=episode_stats,steps=steps)
                adv,ret=agent.buffer.compute_gae(last,agent.gamma,agent.gae_lambda)
                agent.update(adv,ret)
                save(folder/"progress.json",dict(arm=arm,seed=seed,stage=stage,steps=agent.num_timesteps,**env.training_totals))
                if agent.num_timesteps==target:
                    agent.save(str(folder/f"policy_{target}.pt"))
                    subprocess.run([sys.executable,"-m","utils.run_experiment_a",arm,str(seed),"--eval",str(target)],check=True)
        finally:
            env.close()


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("arm",choices=["A0","A0_no_lc_cost","A0_missed_split","A0_prep_only","A0_restart_control",*OBS_TRIALS,"A1","A2","A3","A4"])
    p.add_argument("seed",type=int)
    p.add_argument("--eval",type=int,default=0)
    p.add_argument("--holdout",action="store_true")
    a=p.parse_args()
    if a.eval:
        worker(a.arm,a.seed,a.eval,a.holdout)
    else:
        import msvcrt
        import time
        folder=ROOT/f"{a.arm}_{a.seed}"
        folder.mkdir(parents=True,exist_ok=True)
        with (folder/"train.lock").open("a+b") as lock:
            if lock.tell()==0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            while True:
                try:
                    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                    break
                except OSError:
                    time.sleep(5)
            if not (folder/("eval_650000.json" if a.arm in CONTINUATIONS else "eval_600000.json")).exists():
                worker(a.arm,a.seed)



"""Bounded paired weight-only restarts; frozen N1, reward, routes and PPO settings."""
import os,time,shutil
from pathlib import Path
from utils import navigation_followup as f
from utils.diagnose_n1_seeds import agent
OUT=f.ROOT/'results/n1_seed_finetune_v1'

def main():
    f.base.torch.set_num_threads(1);OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    def status(stage,**kw):f.save(OUT/'status.json',dict(stage=stage,pid=os.getpid(),updated=time.time(),**kw))
    try:
        source_dir=f.OUT/'runs/shared-N1-11';f.cached_run(source_dir)
        hp=f.read(source_dir/'manifest.json')['hp'];budget=200000
        f.save(OUT/'plan.json',dict(**f.stamp(),script_sha=f.base.digest(Path(__file__)),budget_per_arm=budget,seed=11,hp=hp,load='none',mode='N1',routes=f.ROUTES,variants=[],optimizer_reset=True,exact_continuation=False,evaluation_seeds=list(range(40001,40021)),source_steps=[600064,800000],cumulative_steps=[800064,1000000],action_overrides=False))
        for source_step,checkpoint in ((600064,'policy-600064.pt'),(800000,'model.pt')):
            d=OUT/f'from-{source_step}'
            if (d/'complete.json').exists():continue
            if d.exists():raise RuntimeError('Partial run preserved: '+str(d))
            d.mkdir();source=source_dir/checkpoint
            f.save(d/'manifest.json',dict(source=str(source),source_sha=f.base.digest(source),source_steps=source_step,additional_steps=budget,cumulative_steps=source_step+budget,hp=hp,optimizer_reset=True,exact_continuation=False,sources=f.read(source_dir/'manifest.json')['sources'],**f.stamp()))
            p=agent(11,checkpoint)
            status('baseline',source_steps=source_step)
            before=f.evaluate(p,'N1',11,'none',f.ROUTES) if source_step==600064 else f.read(source_dir/'evaluation.json')
            f.save(d/'baseline-evaluation.json',before)
            # Recreate after evaluation to match torch/NumPy initial seeds in each arm.
            p=agent(11,checkpoint);env=f.environment('N1',11,'none',f.ROUTES)
            p.save(str(d/'initial.pt'));log=f.base.Log(d,p,budget,env)
            status('training',source_steps=source_step,target=budget)
            try:
                p.learn(env,budget,logger=log,eval_interval=0,exact_budget=True)
                assert p.num_timesteps==budget and env.route_override_count==0
                p.save(str(d/'model.pt'))
            finally:env.close();log.close()
            status('evaluation',source_steps=source_step)
            after=f.evaluate(p,'N1',11,'none',f.ROUTES)
            f.save(d/'evaluation.json',after)
            f.save(d/'complete.json',dict(steps=budget,pass_gate=f.gate(after,f.ROUTES),model_sha=f.base.digest(d/'model.pt')))
        status('complete')
    except Exception as exc:status('error',error=repr(exc));raise
    finally:lock.unlink()
if __name__=='__main__':main()

"""Matched navigation-only continuation vs 300m lane progress reward."""
import argparse
import concurrent.futures
import os
import subprocess
import sys
import time
from utils import navigation_recovery as n
from utils.train_lane_learning import ProgressReward

b, f, r = n.b, n.f, n.r
OUT = n.OUT


class PrepareEnv(n.AuditEnv):
    def reset(self, *args, **kwargs):
        self.credits=ProgressReward()
        return super().reset(*args, **kwargs)

    def step(self, action):
        v=b.traci.vehicle
        edge=v.getRoadID(self.ego_id);lane=v.getLaneIndex(self.ego_id)
        nav=self.navigation_context()
        obs,reward,done,cut,info=super().step(action)
        extra=0.
        if not done and self.ego_id in v.getIDList() and v.getRoadID(self.ego_id)==edge and not edge.startswith(':'):
            distance=nav['distance']
            extra=self.credits.award(edge,nav['prepare_targets'],lane,v.getLaneIndex(self.ego_id),
                                    distance/3 if distance is not None else None)
        self.extra_total=getattr(self,'extra_total',0.)+extra
        info['prepare_reward']=extra
        return obs,reward+extra,done,cut,info


def evaluate(directory, policy, step, count):
    meta=f.read(directory/'manifest.json');seed=meta['seed'];b.torch.set_num_threads(1)
    agent=b.PPO(obs_dim=47,act_dim=2,**meta['hp']);agent.load(str(policy))
    f.environment=lambda mode,seed,load='none',routes=None,variants=():n.environment(seed,load)
    allrows=[]
    for load in ['none','low']:
        rows=f.evaluate(agent,'N1',seed,load,f.ROUTES,count,())
        allrows+=rows
    r.save(directory/f'eval-{step}.json',allrows)
    summary={}
    for load in ['none','low']:
        rows=[x for x in allrows if x['load']==load]
        a=sum(x['arrival'] for x in rows);c=sum(x['collision'] for x in rows)
        summary[load]=dict(cases=len(rows),arrivals=a,collisions=c,other=len(rows)-a-c,
                          per_route={route:dict(cases=sum(x['route']==route for x in rows),
                            arrivals=sum(x['arrival'] for x in rows if x['route']==route),
                            collisions=sum(x['collision'] for x in rows if x['route']==route)) for route in f.ROUTES})
    r.save(directory/f'eval-{step}.summary.json',dict(step=step,policy_sha=b.digest(policy),results=summary))


def eval_process(directory,policy,step,count):
    subprocess.run([sys.executable,'-X','utf8','-m','utils.navigation_recovery_train',
                    '--evaluate',str(directory),str(policy),str(step),'--count',str(count)],
                   cwd=f.ROOT,check=True,stdout=subprocess.DEVNULL)


class Log(b.Log):
    def __init__(self,*args,count):
        super().__init__(*args);self.next_eval=50000;self.count=count
    def log_train(self,step,metrics,verbose=False):
        super().log_train(step,dict(metrics,prepare_reward_total=getattr(self.env,'extra_total',0.)),False)
        if step>=self.next_eval or step==self.budget:
            p=self.directory/f'policy-{step}.pt';self.agent.save(str(p))
            r.save(self.directory/'status.json',dict(stage='evaluating',step=step,pid=os.getpid(),updated=time.time()))
            eval_process(self.directory,p,step,self.count)
            self.next_eval+=50000
        r.save(self.directory/'status.json',dict(stage='training',step=step,pid=os.getpid(),updated=time.time()))


def train(spec):
    mode,seed,smoke=spec;b.torch.set_num_threads(1)
    directory=OUT/('training-smoke' if smoke else 'runs')/f'{mode}-{seed}'
    if (directory/'complete.json').exists():return str(directory)
    if directory.exists():raise RuntimeError('Partial run preserved: '+str(directory))
    directory.mkdir(parents=True)
    source=r.sources('baseline',seed)/'policy-600064.pt'
    old=f.read(source.parent/'manifest.json');budget=2048 if smoke else 200000
    count=1 if smoke else 3
    hashes={str(f.ROOT/p):b.digest(f.ROOT/p) for p in r.c.SOURCES}
    hashes[str(source)]=b.digest(source)
    hashes[str(n.OUT/'traffic_v2/low/highway.rou.xml')]=b.digest(n.OUT/'traffic_v2/low/highway.rou.xml')
    r.save(directory/'manifest.json',dict(mode=mode,seed=seed,hp=old['hp'],budget=budget,
        source=str(source),source_sha=b.digest(source),map_sha=b.digest(b.MAP/'network.net.xml'),
        commit=b.COMMIT,hashes=hashes,forced_correction=False,optimizer='fresh in both arms',
        prepare_reward='0.1 per newly gained target lane level within300m' if mode=='prepare300' else 'none',
        action=old['action'],base_reward=old['reward'],evaluation_count=count))
    agent=b.PPO(obs_dim=47,act_dim=2,buffer=b.RolloutBuffer(),**old['hp']);agent.load(str(source))
    e=n.environment(seed,'low',PrepareEnv if mode=='prepare300' else n.AuditEnv)
    logger=Log(directory,agent,budget,e,count=count)
    try:
        eval_process(directory,source,0,count)
        agent.learn(e,budget,logger=logger,eval_interval=0,exact_budget=True)
        assert agent.num_timesteps==budget and e.route_override_count==0
        agent.save(str(directory/'model.pt'))
        f.verify_hashes(hashes)
        r.save(directory/'complete.json',dict(steps=budget,model_sha=b.digest(directory/'model.pt')))
        r.save(directory/'status.json',dict(stage='complete',step=budget))
    except Exception as exc:
        r.save(directory/'status.json',dict(stage='error',error=repr(exc)));raise
    finally:e.close();logger.close()
    return str(directory)


def main():
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true')
    p.add_argument('--evaluate',nargs=3);p.add_argument('--count',type=int,default=3);args=p.parse_args()
    if args.evaluate:
        from pathlib import Path
        d,model,step=args.evaluate;evaluate(Path(d),Path(model),int(step),args.count);return
    if (OUT/'PAUSED_BY_USER').exists():
        raise RuntimeError('AV experiments paused by user: validate HV-only traffic first')
    lock=OUT/'training.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        specs=[(m,s,args.smoke) for m in ['baseline','prepare300'] for s in ([11] if args.smoke else [11,22,33])]
        r.save(OUT/'training-status.json',dict(stage='running',pid=os.getpid(),jobs=len(specs)))
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
            for result in pool.map(train,specs):print(result,flush=True)
        r.save(OUT/'training-status.json',dict(stage='complete',jobs=len(specs)))
    except Exception as exc:
        r.save(OUT/'training-status.json',dict(stage='error',error=repr(exc)));raise
    finally:lock.unlink(missing_ok=True)


if __name__=='__main__':main()

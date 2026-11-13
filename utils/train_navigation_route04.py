"""Route04-only N0/N1/N2 comparison; no action teacher, no implicit resume."""
import argparse,time,os,shutil
from utils.check_toegyewon_only import *
from utils.ic_campaign import Checkpoints,RolloutBuffer
from env.navigation_observation import NavigationEnv,RouteNavigation
ROUTE='route_04'
DEST=ROOT/'results/navigation_route04_v1'
PLAN=json.loads((ROOT/'docs/experiments/ic-navigation-plan-v1.json').read_text())
LENGTHS={e:max(float(l.get('length')) for l in x.findall('lane')) for e,x in EDGES.items()}
INTERNAL={l.get('id'):float(l.get('length')) for x in XML.findall('edge') if x.get('function')=='internal' for l in x.findall('lane')}
LINK_LENGTHS={}
for c in XML.findall('connection'):
 if c.get('from') in EDGES and c.get('to') in EDGES:
  key=(c.get('from'),c.get('to'));LINK_LENGTHS[key]=max(LINK_LENGTHS.get(key,0.),INTERNAL.get(c.get('via'),0.))
NAV=RouteNavigation({e:len(x.findall('lane')) for e,x in EDGES.items()},ROAD_NEW['connections'],LENGTHS,link_lengths=LINK_LENGTHS)

def stamp():
 return dict(git=COMMIT,network_sha256=digest(MAP/'network.net.xml'),simulation_seed_policy='training: seeded per-episode generator; evaluation: explicit 20001..20020')

def environment(mode,seed,lane='best',speed='max',route=None):
 route=route or ROUTE
 road=dict(ROAD_NEW,routes={route:MAN['routes'][route]})
 return NavigationEnv(str(MAP/'review.sumocfg'),road,dict(EGO,depart_lane=lane,depart_speed=speed),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),(),seed,observation_mode=mode,navigation=NAV)

class Log(Checkpoints):
 def __init__(self,directory,agent,budget,env):
  super().__init__(directory,agent,budget);self.env=env
  if self.writer is None:raise RuntimeError('TensorBoard unavailable')
 def log_train(self,step,metrics,verbose=False):
  assert all(np.isfinite(v) for k,v in metrics.items() if k!="ep_rew_mean" and isinstance(v,(float,int)))
  super().log_train(step,metrics,verbose=False)
  save(self.directory/'action-audit.json',dict(checked_steps=self.env.action_checks,route_override_count=self.env.route_override_count,episode_seeds=self.env.episode_seeds))

def evaluate(agent,mode):
 rows=[]
 # Distinct physical start cases, not 20 copies of the same deterministic episode.
 for i in range(20):
  lane=str(i%4);speed=str((i//4)*5)
  env=environment(mode,11,lane,speed)
  try:
   try:obs,_=env.reset(seed=20001+i)
   except RuntimeError as exc:
    rows.append(dict(seed=20001+i,lane=lane,speed=speed,insertion_failure=True,error=str(exc),arrival=False,collision=False));continue
   trace=TimeoutTrace();teleports=0
   while True:
    if env.step_count%5==0:trace.sample(env)
    obs,_,done,cut,info=env.step(agent.predict(obs,deterministic=True));teleports+=traci.simulation.getStartingTeleportNumber()
    if done or cut:break
   rows.append(dict(seed=20001+i,lane=lane,speed=speed,arrival=bool(info['arrived']) and not teleports,collision=bool(info['collided']),timeout=bool(cut and not done),teleports=teleports,action_checks=env.action_checks,route_overrides=env.route_override_count,diagnostic=trace.result()))
  finally:env.close()
 return rows

def run(mode,seed,budget,smoke=False):
 directory=DEST/('smoke' if smoke else 'runs')/f'{mode}-{seed}-{budget}'
 if (directory/'complete.json').exists():return
 if directory.exists():raise RuntimeError(f'Partial run preserved; explicit recovery needed: {directory}')
 directory.mkdir(parents=True)
 hp=dict(PLAN['hparams'],seed=seed)
 env=environment(mode,seed);agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,buffer=RolloutBuffer(),**hp)
 snapshots=directory/'snapshot';snapshots.mkdir()
 sources=['env/navigation_observation.py','env/ic_experiment.py','env/sumo_env.py','utils/train_navigation_route04.py','utils/train_navigation_route14.py','algorithms/ppo.py','utils/networks.py','train.py','env/mdp_config.py','env/road_config.py','maps/toegyewon_only/network.net.xml','maps/toegyewon_only/routes.rou.xml','maps/toegyewon_only/review.sumocfg']
 hashes={}
 for src in sources:
  target=snapshots/src;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/src,target);hashes[src]=digest(target)
 save(directory/'manifest.json',dict(mode=mode,seed=seed,budget=budget,hp=hp,route=ROUTE,observation_schema=mode+'-37-v1',action_overrides=False,road=env.road if hasattr(env,'road') else ROAD_NEW,ego=EGO,simulation=SIMULATION,observation=OBSERVATION,action=ACTION,reward=REWARD,traffic=dict(TRAFFIC,vehs_per_hour=0,prefill={'enabled':False}),actual_depart_lane='best',actual_depart_speed='max',hashes=hashes,**stamp()))
 agent.save(str(directory/'initial.pt'))
 logger=Log(directory,agent,budget,env);started=time.monotonic()
 try:
  agent.learn(env,budget,logger=logger,eval_interval=0,exact_budget=True)
  agent.save(str(directory/'model.pt'))
 finally:env.close();logger.close()
 assert agent.num_timesteps==budget
 evaluations=[] if smoke else evaluate(agent,mode)
 save(directory/'evaluation.json',evaluations)
 save(directory/'complete.json',dict(mode=mode,seed=seed,steps=agent.num_timesteps,seconds=time.monotonic()-started,arrivals=sum(r['arrival'] for r in evaluations),eval_cases=len(evaluations),route_override_count=env.route_override_count,initial_sha=digest(directory/'initial.pt'),**stamp()))

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['smoke','train']);a=p.parse_args()
 torch.set_num_threads(1);DEST.mkdir(exist_ok=True,parents=True)
 if digest(MAP/'network.net.xml')!=PLAN['map_sha256']:raise RuntimeError('Map differs from frozen plan')
 lock=DEST/'active.lock'
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for seed in ((11,) if a.stage=='smoke' else (11,22,33)):
   for mode in ('N0','N1','N2'):
    save(DEST/'status.json',dict(stage=a.stage,mode=mode,seed=seed,pid=os.getpid(),**stamp()))
    run(mode,seed,2048 if a.stage=='smoke' else 200000,a.stage=='smoke')
  save(DEST/'status.json',dict(stage=a.stage+'_complete',**stamp()))
 except Exception as exc:
  save(DEST/'status.json',dict(stage='error',error=repr(exc),**stamp()));raise
 finally:lock.unlink()
if __name__=='__main__':main()

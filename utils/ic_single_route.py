"""Paired no-traffic single-route experiment; never changes shared map/reward."""
import argparse
import json
import subprocess
import time
import numpy as np
from utils.ic_campaign import ROOT, PPO, torch, save, digest, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD, TRAFFIC, HPARAMS, RolloutBuffer, Checkpoints, snapshot_configs
from utils.ic_no_traffic_check import DEST as PREFLIGHT
from env.ic_experiment import ICExperimentEnv
from env.sumo_env import traci
from utils.ic_timeout_trace import TimeoutTrace
OUT=ROOT/'results/ic_single_route_v1'
EVAL=[dict(id=f'l{l}-v{v}',lane=str(l),speed=str(v)) for l in range(6) for v in ((5,15,25) if l<3 else (0,5,15))]+[dict(id='best-stop',lane='best',speed='0'),dict(id='best-max',lane='best',speed='max')]
TRAIN=[dict(lane=str(l),speed=str(v)) for l in range(6) for v in ((7,17,23) if l<3 else (3,7,13))]

def route_features(env):
    """Distance along external route edges; internal connector lengths excluded."""
    v=traci.vehicle; edge=v.getRoadID(env.ego_id)
    if edge.startswith(':'):return None,0
    path=env.routes[env.episode_route];idx=v.getRouteIndex(env.ego_id)
    lane=v.getLaneIndex(env.ego_id)
    distance=traci.lane.getLength(v.getLaneID(env.ego_id))-v.getLanePosition(env.ego_id)
    for j in range(idx,len(path)-1):
        src,dst=path[j:j+2];targets=env.links[src][dst]
        if len(env.links[src])>1 and targets and len(targets)<env.counts[src]:
            # Future edges may use different lane numbering: use current best-lane guidance.
            offset=min(targets,key=lambda x:(abs(x-lane),x))-lane if j==idx else env.context()[6]
            return max(0.,distance),offset
        if j+1<len(path)-1:distance+=traci.lane.getLength(path[j+1]+'_0')
    return None,0

class SingleRouteEnv(ICExperimentEnv):
    def __init__(self,mode,seed=11):
        self.mode=mode;self.start_rng=np.random.default_rng(seed);self.start_schedule=[]
        super().__init__(str(PREFLIGHT/'map/highway.sumocfg'),ROAD,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,demo_vehicle=False,vehs_per_hour=0),(),seed)
    def reset(self,seed=None,options=None):
        case=(options or {}).get('case')
        if case is None:
            if not self.start_schedule:self.start_schedule=list(self.start_rng.permutation(len(TRAIN)))
            case=TRAIN[self.start_schedule.pop()]
        self.ego_depart_lane=case['lane'];self.ego_depart_speed=case['speed']
        return super().reset(seed=seed,options={'route':'south_to_east'})
    def _get_obs(self):
        obs=super()._get_obs()
        if self.mode=='corrected' and self.ego_id in traci.vehicle.getIDList():
            distance,offset=route_features(self)
            obs[-5]=min(distance/200,1) if distance is not None else -1
            obs[-4]=np.clip(offset/3,-1,1)
        return obs
    def step(self,action):
        assert set(traci.vehicle.getIDList()) <= {self.ego_id}
        return super().step(action)

def episode(env,case,agent=None):
    obs,_=env.reset(seed=1001,options={'case':case});trace=TimeoutTrace()
    initial=dict(lane=traci.vehicle.getLaneIndex(env.ego_id),speed=traci.vehicle.getSpeed(env.ego_id),obs=obs.tolist())
    while True:
        if env.step_count%5==0:trace.sample(env)
        if agent is None:
            ctx=env.context();delta=ctx[2]-traci.vehicle.getSpeed(env.ego_id)
            scale=env.max_accel if delta>=0 else env.max_decel
            action=[np.clip(delta/(scale*env.step_length),-1,1),np.sign(ctx[6])]
        else: action=agent.predict(obs,deterministic=True)
        obs,_,done,cut,info=env.step(action)
        if done or cut:break
    return dict(case=case,initial=initial,arrival=bool(info['arrived']),collision=bool(info['collided']),timeout=bool(cut and not done),seconds=env.step_count*env.step_length,diagnostic=trace.result() if cut and not done else None)

def validate():
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'conditions.json',dict(evaluation=EVAL,training=TRAIN,position=0,route='south_to_east',budget=200000,seed=11))
    env=SingleRouteEnv('original')
    try:
        rows=[]
        for case in EVAL:
            try: row=episode(env,case)
            except RuntimeError as exc:
                row=dict(case=case,arrival=False,collision=False,timeout=False,invalid_start=True,error=str(exc));env.close()
            rows.append(row)
            save(OUT/'start-validation.json',rows)
        if not all(r['arrival'] for r in rows):
            save(OUT/'status.json',dict(stage='start_validation_failed',cases=len(rows),arrivals=sum(r['arrival'] for r in rows)))
            raise RuntimeError('Start validation failed; preserve cases and revise declared starting envelope')
        training_rows=[]
        for case in TRAIN:
            training_rows.append(episode(env,case))
            save(OUT/'training-start-validation.json',training_rows)
        assert all(r['arrival'] for r in training_rows)
        # Verify only the two intended observation coordinates differ at identical starts.
        for case in EVAL:
            original,_=env.reset(seed=1001,options={'case':case})
            corrected=SingleRouteEnv('corrected')
            # libsumo is singleton: close original before creating the second simulation.
            env.close()
            try:
                modified,_=corrected.reset(seed=1001,options={'case':case})
                keep=[i for i in range(len(original)) if i not in (len(original)-5,len(original)-4)]
                assert np.array_equal(original[keep],modified[keep])
                assert original[-5]==-1 and modified[-5]>=0
                assert np.isfinite(modified).all()
            finally:corrected.close()
    finally:env.close()
    save(OUT/'status.json',dict(stage='starts_validated',cases=len(rows),arrivals=sum(r['arrival'] for r in rows)))
    if not all(r['arrival'] for r in rows):raise RuntimeError('Start validation failed; no automatic training')

def train(mode):
    directory=OUT/mode;directory.mkdir(parents=True,exist_ok=True)
    if (directory/'evaluation.json').exists():return
    env=SingleRouteEnv(mode);hp=dict(HPARAMS,seed=11,device='cpu')
    agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,buffer=RolloutBuffer(),**hp)
    manifest=dict(mode=mode,hp=hp,budget=200000,seed=11,network_sha256=digest(PREFLIGHT/'map/highway.net.xml'),git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),reward=REWARD,action=ACTION,simulation=SIMULATION,train_conditions=TRAIN,eval_conditions=EVAL)
    save(directory/'manifest.json',manifest);snapshot_configs(str(directory))
    save(directory/'status.json',dict(stage='training',mode=mode))
    log=Checkpoints(directory,agent,200000);started=time.monotonic()
    try:
        if not (directory/'model.pt').exists():
            agent.learn(env,200000,logger=log,eval_interval=0,exact_budget=True)
            agent.save(str(directory/'model.pt'))
            save(directory/'timing.json',dict(seconds=time.monotonic()-started))
        else:agent.load(str(directory/'model.pt'))
        rows=[]
        for case in EVAL:
            rows.append(episode(env,case,agent));save(directory/'evaluation-partial.json',rows)
        save(directory/'evaluation.json',dict(rows=rows,arrival=sum(r['arrival'] for r in rows)/len(rows),collision=sum(r['collision'] for r in rows)/len(rows),timeout=sum(r['timeout'] for r in rows)/len(rows),model_sha256=digest(directory/'model.pt')))
    finally:env.close();log.close()
    save(directory/'status.json',dict(stage='evaluation_complete',mode=mode))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['validate','original','corrected']);args=parser.parse_args()
    torch.set_num_threads(1)
    if args.stage=='validate':validate()
    else:
        rows=json.loads((OUT/'start-validation.json').read_text())
        assert len(rows)==20 and all(r['arrival'] for r in rows)
        train(args.stage)

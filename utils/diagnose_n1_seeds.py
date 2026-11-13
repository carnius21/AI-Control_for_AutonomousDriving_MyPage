"""Read-only N1 policy diagnosis on the frozen no-traffic environment."""
import json
from pathlib import Path
from utils import navigation_followup as f

OUT=f.ROOT/'results/n1_seed_diagnosis'

def agent(seed, checkpoint='model.pt'):
    d=f.OUT/'runs'/f'shared-N1-{seed}'
    f.cached_run(d)
    hp=f.read(d/'manifest.json')['hp']
    p=f.base.PPO(obs_dim=37,act_dim=2,**hp)
    p.load(str(d/checkpoint))
    return p

def run(policy, route, others, name):
    env=f.environment('N1',11,'none',[route]); rows=[]
    try:
        obs,_=env.reset(seed=40001,options={'route':route})
        while True:
            v=f.base.traci.vehicle; ego=env.ego_id
            lane=v.getLaneID(ego)
            row=dict(step=env.step_count,t=env.step_count*env.step_length,edge=v.getRoadID(ego),lane=v.getLaneIndex(ego),position=v.getLanePosition(ego),remaining=f.base.traci.lane.getLength(lane)-v.getLanePosition(ego),speed=v.getSpeed(ego),nav=env.navigation_context(),obs=obs.tolist(),cross={str(s):p.predict(obs,deterministic=True).tolist() for s,p in others.items()})
            action=policy.predict(obs,deterministic=True)
            obs,reward,done,cut,info=env.step(action)
            row.update(action=action.tolist(),command=info['lane_change'],applied=bool(info['lane_change_applied']),reward=float(reward))
            rows.append(row)
            if done or cut:break
        summary=dict(name=name,route=route,arrival=bool(info['arrived']),collision=bool(info['collided']),timeout=bool(cut and not done),seconds=env.step_count*env.step_length,final=rows[-1],overrides=env.route_override_count)
        f.save(OUT/(name+'-'+route+'.json'),dict(summary=summary,trace=rows))
        print(name,route,summary['arrival'],summary['seconds'],flush=True)
        return summary
    finally:env.close()

def main():
    f.base.torch.set_num_threads(1);OUT.mkdir(exist_ok=True,parents=True)
    policies={s:agent(s) for s in (11,22,33)}
    summaries=[]
    for s,p in policies.items():
        for route in ('route_03','route_04','route_05','route_13','route_14'):
            summaries.append(run(p,route,policies,f'seed{s}-800000'))
    for step in (200704,401408,600064):
        p=agent(11,f'policy-{step}.pt')
        for route in ('route_04','route_05'):
            summaries.append(run(p,route,policies,f'seed11-{step}'))
    topology={}
    for route in ('route_04','route_05'):
        path=f.base.MAN['routes'][route]
        topology[route]=[dict(edge=e,length=f.base.LENGTHS[e],lanes=f.COUNTS[e],next=n,links=f.base.NAV.links[e,n]) for e,n in zip(path,path[1:])]
    f.save(OUT/'summary.json',summaries);f.save(OUT/'topology.json',topology)
    f.save(OUT/'manifest.json',dict(**f.stamp(),script_sha=f.base.digest(Path(__file__)),source_models={str(s):f.base.digest(f.OUT/'runs'/f'shared-N1-{s}'/'model.pt') for s in policies},simulation_seed=40001,interval=.2,action_overrides=False))

if __name__=='__main__':main()

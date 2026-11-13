"""Diagnostic only: keep acceleration fixed, compare greedy vs sampled lane choice."""
import concurrent.futures
from utils import evaluate_clarity_checkpoints as audit

c=audit.c;f=c.f


class LaneSamplePolicy:
    def __init__(self,agent):self.agent=agent
    def predict(self,obs,deterministic=True):
        torch=f.base.torch
        with torch.no_grad():
            tensor=torch.as_tensor(obs,dtype=torch.float32,device=self.agent.device).unsqueeze(0)
            mu,_,logits,_=self.agent.policy(tensor)
            idx=int(torch.distributions.Categorical(logits=logits).sample().item())
            return f.base.np.array([float(mu.item()),self.agent.policy.LANE_CMDS[idx]],dtype=f.base.np.float32)


def run(spec):
    f.base.torch.set_num_threads(1)
    name,route=spec;source=c.OUT/'runs'/name;meta=f.read(source/'manifest.json')
    cases=f.read(source/'evaluation.json')
    case=next(r for r in cases if r['route']==route and not r['arrival'])
    p=f.base.PPO(obs_dim=47,act_dim=2,**meta['hp']);p.load(str(source/'model.pt'))
    result=dict(run=name,case={k:case[k] for k in ('route','lane','speed','simulation_seed')})
    result['greedy']=audit.evaluate_cases(p,meta['condition'],meta['seed'],[case])[0]
    # Replay same deterministic trajectory and record actual distribution at its stopped state.
    env=c.environment(meta['condition'],meta['seed'],case['lane'],case['speed'])
    try:
        obs,_=env.reset(seed=case['simulation_seed'],options={'route':route})
        while True:
            with f.base.torch.no_grad():
                t=f.base.torch.as_tensor(obs,dtype=f.base.torch.float32).unsqueeze(0)
                _,_,logits,_=p.policy(t);probs=f.base.torch.softmax(logits,dim=-1).squeeze(0).tolist()
            obs,_,done,cut,_=env.step(p.predict(obs,deterministic=True))
            if done or cut:break
        result['final_lane_probabilities']=dict(zip(map(str,p.policy.LANE_CMDS),probs))
    finally:env.close()
    result['lane_sampled']=[]
    for seed in (701,702,703):
        f.base.torch.manual_seed(seed)
        row=audit.evaluate_cases(LaneSamplePolicy(p),meta['condition'],meta['seed'],[case])[0]
        result['lane_sampled'].append(dict(row,sampling_seed=seed))
    f.save(audit.OUT/f'sampling-{name}.json',result)
    return result


if __name__=='__main__':
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        rows=list(pool.map(run,[('baseline-33','route_08'),('validity-11','route_04'),('lookahead-22','route_03')]))
    f.save(audit.OUT/'sampling-summary.json',rows)

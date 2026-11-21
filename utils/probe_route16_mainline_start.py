from concurrent.futures import ProcessPoolExecutor
from utils.experiment_a import ROOT,make,m,torch
import json

def probe(s):
 arm='sensor200_pass'
 p=ROOT/f'{arm}_{s}'
 e=make('high_real_ratio',arm,s,p/'route16_startlane_check'); e.ego_depart_lane='1'
 torch.set_num_threads(1)
 a=m.PPO(obs_dim=40,act_dim=2,buffer=m.RolloutBuffer(),seed=s,device='cpu',hidden_sizes=(256,256))
 a.load(str(p/'policy_650000.pt'));rows=[]
 try:
  for seed in (41016,41116,41216):
   o,_=e.reset(seed=seed,options={'route':'route_16'});initial=e.snapshot[1];assert initial==1
   first_right=None;seen=set()
   for i in range(3000):
    edge,l,path,k,j,d,_,v,rem=e.snapshot
    seen.add(edge)
    act=a.predict(o);o,_,done,cut,info=e.step(act)
    if edge=='86198728' and l==1 and e.snapshot and e.snapshot[0]==edge and e.snapshot[1]==0 and first_right is None:first_right=round(rem,1)
    if done or cut:
     rows.append(dict(s=s,seed=seed,initial=initial,passed=('86198725' in seen),result=('arrival' if info['arrived'] else 'collision' if info['collided'] else 'timeout' if cut else 'other'),edge=edge,lane=l,right_at=first_right));break
 finally:e.close()
 return rows

if __name__=='__main__':
 with ProcessPoolExecutor(3) as pool:r=sum(pool.map(probe,[11,22,33]),[])
 (ROOT/'route16_mainline_start_probe.json').write_text(json.dumps(r,indent=2))
 print(r)

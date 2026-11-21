from utils.experiment_a import ROOT,make,m,SIZE,torch,traci
from concurrent.futures import ProcessPoolExecutor
import json
from collections import Counter
def replay(c):
 s,r=c
 p=ROOT/f'A0_missed_split_{s}';torch.set_num_threads(1)
 e=make('high_real_ratio','A0_missed_split',s,p/'timeout_locations'/str(r['seed']))
 a=m.PPO(obs_dim=SIZE,act_dim=2,buffer=m.RolloutBuffer(),seed=s,device="cpu",hidden_sizes=(256,256),n_steps=2048,n_epochs=10,minibatch_size=64,lr=.0001,lane_entropy_coef=.002,lane_keep_bias=1.)
 a.load(str(p/'policy_600000.pt'));o,_=e.reset(seed=r['seed'],options={'route':r['route']})
 try:
  lastmove=0;tail=Counter()
  for i in range(3000):
   edge,lane,path,k,j,d,_,v,rem=e.snapshot
   act=a.predict(o)
   if v>.1:lastmove=i
   if i>=2950:
    lead=traci.vehicle.getLeader(e.ego_id,50)
    nxt=path[k+1] if k+1<len(path) else '-'
    targets=sorted(e.links.get(edge,{}).get(nxt,[]))
    tail[(edge,lane,nxt,tuple(targets),round(rem,1),round(v,1),bool(lead and lead[0]),act[0]>0)]+=1
   o,_,done,cut,info=e.step(act)
   if done or cut:break
  assert cut and i==2999
  return (s,r['route'],r['seed'],round((2999-lastmove)*.2,1),tail.most_common(3))
 finally:e.close()
if __name__=='__main__':
 cases=[(s,r) for s in (11,22,33) for r in json.loads((ROOT/f'A0_missed_split_{s}'/'eval_600000.json').read_text()) if r['outcome']=='timeout' and not r['wrong_timeout']]
 with ProcessPoolExecutor(6) as ex:
  for row in ex.map(replay,cases):print(row,flush=True)


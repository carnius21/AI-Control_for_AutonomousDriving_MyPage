import json
from concurrent.futures import ProcessPoolExecutor
from utils.experiment_a import ROOT,make,m,torch
from utils.failure_log import FailureLog
def replay(job):
 s,group=job
 p=ROOT/f'prep_both_{s}'
 runs=json.loads((p/'eval_600000.json').read_text())
 e=make('high_real_ratio','prep_both',s,p/'incident_maps'/str(group))
 torch.set_num_threads(1)
 a=m.PPO(obs_dim=40,act_dim=2,buffer=m.RolloutBuffer(),seed=s,device='cpu',hidden_sizes=(256,256))
 a.load(str(p/'policy_600000.pt'));rows=[]
 try:
  for i,r in enumerate(runs):
   if i%3!=group or r['outcome']=='arrival':continue
   o,_=e.reset(seed=r['seed'],options={'route':r['route']});log=FailureLog()
   while True:
    log.before(e,o);o,_,d,c,info=e.step(a.predict(o))
    outcome='collision' if info['collided'] else 'arrival' if info['arrived'] else 'timeout' if c else None
    note=log.after(e,info,outcome)
    if d or c:
     assert outcome==r['outcome']
     rows.append(dict(model=s,route=r['route'],seed=r['seed'],outcome=outcome,**note));break
 finally:e.close()
 return rows
if __name__=='__main__':
 with ProcessPoolExecutor(9) as pool:data=[r for part in pool.map(replay,[(s,g) for s in (11,22,33) for g in range(3)]) for r in part]
 assert len(data)==88
 (ROOT/'prep_both_incidents.json').write_text(json.dumps(data,indent=2))

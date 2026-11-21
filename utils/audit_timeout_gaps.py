from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import gzip,json,itertools,csv
from utils.audit_front_timeouts import DEST
from utils.front_trials import setup,traci

def audit(f):
    route=f.name[:8]
    seed=int(f.name[9:14])
    with gzip.open(f,'rt') as stream: trace=json.load(stream)
    last=max(i for i,x in enumerate(trace) if x['spd']>.1)
    end=trace[-1]
    folder,env,agent=setup('brake',str(DEST/'maps'/str(seed)))
    agent.load(str(folder/'policy_100000.pt'))
    samples=[]
    try:
        obs,_=env.reset(seed=seed,options={'route':route})
        path=env.snapshot[2]
        j=next(k for k in range(len(path)-1) if tuple(path[k:k+2])==(end['edge'],end['nxt']))
        targets=set(env.links[path[j]][path[j+1]])
        back={j:(targets,0)}
        for k in reversed(range(j)):
            targets={a for a,b in env.navigation.links[path[k],path[k+1]] if b in targets}
            back[k]=(targets,back[k+1][1]+env.navigation.lengths[path[k+1]]+env.navigation.link_lengths.get((path[k],path[k+1]),0))
        for i in range(last+1):
            edge,lane,path,k,_,_,sides,v,rem=env.snapshot
            assert edge==trace[i]['edge'] and lane==trace[i]['lane'] and abs(v-trace[i]['spd'])<.001
            act=agent.predict(obs,deterministic=True)
            if edge==path[k] and k in back:
                targets,extra=back[k];d=rem+extra
                if 5<=d<=400 and targets and lane not in targets and edge not in env.solid:
                    direction=1 if min(targets,key=lambda g:abs(g-lane))>lane else -1
                    gaps=[]
                    for side,mode in zip(sides[direction],env._NEIGHBOR_MODES[direction]):
                        opts=[side] if side else []
                        for vehicle,gap in traci.vehicle.getNeighbors(env.ego_id,mode):
                            if gap<=env.visibility:opts.append((gap,traci.vehicle.getSpeed(vehicle)))
                        gaps.append(min(opts) if opts else None)
                    front,rear=gaps
                    def permit(h):
                        for n,item in enumerate(gaps):
                            if item:
                                g,s=item
                                if g<max(3.5+(.35*s if n else .3*v),3.5+h*max(0,s-v if n else v-s)):return False
                        return True
                    samples.append(dict(i=i,d=d,v=v,edge=edge,front=front and front[0],rear=rear and rear[0],df=front and front[1]-v,dr=rear and rear[1]-v,ok=permit(2),strict=permit(3),correct=trace[i]['lc']==direction))
            obs,*_=env.step(act)
    finally:env.close()
    best={}
    for label in ('ok','strict'):
        wins=[]
        for _,g in itertools.groupby((x for x in samples if x[label]),key=(lambda c:lambda x:x['i']-next(c))(itertools.count())):
            wins.append(list(g))
        best[label]=max(wins,key=len,default=[])
    with gzip.open(DEST/(f.stem+'.gaps.gz'),'wt') as out:json.dump(samples,out)
    t=best['ok']; rep=t[len(t)//2] if t else {}
    return [route,seed,len(samples),round(.2*len(t),1),round(.2*len(best['strict']),1),round(t[0]['d'],1) if t else None,round(t[-1]['d'],1) if t else None,sum(x['correct'] for x in t),*[round(rep[k],1) if rep.get(k)!=None else None for k in ('front','df','rear','dr')],sum(x['correct'] for x in samples)]
if __name__=='__main__':
    files=sorted(DEST.glob('route_*.json.gz'))
    with ProcessPoolExecutor(6) as p:rows=list(p.map(audit,files))
    with (DEST/'gap_windows.csv').open('w',newline='',encoding='utf-8-sig') as out:
        w=csv.writer(out);w.writerow('route seed eligible_steps window_s strict_s start_m end_m target_cmds_window front_m front_relative_mps rear_m rear_relative_mps target_cmds_total'.split());w.writerows(rows)
    for row in rows:print(row)


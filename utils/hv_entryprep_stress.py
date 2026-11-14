"""HV robustness audit: immutable map, independent stress factors, six workers."""
import concurrent.futures as cf
import functools,json,os,shutil,subprocess
from pathlib import Path
import xml.etree.ElementTree as E
from utils import hv_flow_audit as a
from utils.hv_flow_repair import init_worker
from utils.hv_measured_traffic import allocate
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/hv_entryprep_stress_20261113'
MODES=['reference','proportional','north_exits','south_exits','east_exit','compressed','bus10','violator5','krauss','idm','eidm','acc']
def prepare(mode):
 d=OUT/'inputs'/mode;d.mkdir(parents=True,exist_ok=True)
 for n in ['network.net.xml','highway.rou.xml','run.sumocfg']:shutil.copy2(ROOT/'scenarios/hv_high15000_entryprep'/n,d/n)
 tree=E.parse(d/'highway.rou.xml');flows=tree.findall('flow');counts={f.get('route'):int(f.get('number')) for f in flows}
 if mode=='proportional':
  base=E.parse(ROOT/'scenarios/hv_stable/highway.rou.xml').findall('flow')
  counts=dict(zip([f.get('route') for f in base],allocate(15000,[float(f.get('vehsPerHour')) for f in base])))
 if mode in ['north_exits','south_exits','east_exit']:
  src,targets,amount={'north_exits':('route_16',['route_13','route_14','route_15'],1800),'south_exits':('route_06',['route_03','route_04','route_05'],1800),'east_exit':('route_08',['route_07'],600)}[mode]
  counts[src]-=amount
  for t in targets:counts[t]+=amount//len(targets)
 for f in flows:f.set('number',str(counts[f.get('route')]));f.set('end','2700' if mode=='compressed' else '3600')
 dist=tree.find('vTypeDistribution');types=dist.get('vTypes').split();weights=[.35,.30,.20,.15];bus=.10 if mode=='bus10' else .05;viol=.05 if mode=='violator5' else .02
 if mode in ['krauss','idm','eidm','acc']:weights=[float(x==mode) for x in ['krauss','idm','eidm','acc']]
 probs=[(1-bus)*(1-viol)*w for w in weights]+[(1-bus)*viol*w for w in weights]+[bus]
 dist.set('probabilities',' '.join(map(str,probs)))
 assert sum(counts.values())==15000 and abs(sum(probs)-1)<1e-9
 tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
 a.save(d/'manifest.json',dict(mode=mode,counts=counts,probabilities=dict(zip(types,probs)),demand_end=2700 if mode=='compressed' else 3600,planned=15000,commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),code_sha=a.sha(Path(__file__)),files={n:a.sha(d/n) for n in ['network.net.xml','highway.rou.xml','run.sumocfg']}))
def main():
 OUT.mkdir(parents=True,exist_ok=True);lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for m in MODES:prepare(m)
  a.save(OUT/'status.json',dict(stage='running',pid=os.getpid(),total=36))
  with cf.ProcessPoolExecutor(max_workers=6,initializer=init_worker,initargs=(str(OUT),)) as pool:
   fs={pool.submit(functools.partial(a.run,horizon=7200,junction_checks=True),(m,s)):(m,s) for m in MODES for s in [8101,8102,8103]}
   errors=[]
   for f in cf.as_completed(fs):
    try:print(f.result(),flush=True)
    except Exception as exc:errors.append(dict(case=fs[f],error=repr(exc)));a.save(OUT/'errors.json',errors)
  a.save(OUT/'status.json',dict(stage='error' if errors else 'complete',errors=errors))
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

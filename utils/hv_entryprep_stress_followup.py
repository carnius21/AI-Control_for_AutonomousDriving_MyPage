"""Separate diagnostics: longer drainage horizon and departure lane sensitivity."""
import concurrent.futures as cf,functools,os,shutil
import xml.etree.ElementTree as E
from utils import hv_flow_audit as a
from utils.hv_flow_repair import init_worker
ROOT=a.ROOT
OUT=ROOT/'results/hv_entryprep_followup_20261113'
def main():
 OUT.mkdir(parents=True,exist_ok=True);lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for mode,src in [('south_drain','south_exits'),('free_departure','reference')]:
   d=OUT/'inputs'/mode;d.mkdir(parents=True,exist_ok=True)
   for n in ['network.net.xml','highway.rou.xml','run.sumocfg']:shutil.copy2(ROOT/'results/hv_entryprep_stress_20261113/inputs'/src/n,d/n)
   if mode=='free_departure':
    tree=E.parse(d/'highway.rou.xml')
    for f in tree.findall('flow'):f.set('departLane','free')
    tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
   a.save(d/'manifest.json',dict(mode=mode,source=src,horizon=10800,code_hash=a.sha(__import__('pathlib').Path(__file__)),files={n:a.sha(d/n) for n in ['network.net.xml','highway.rou.xml','run.sumocfg']}))
  a.save(OUT/'status.json',dict(stage='running',pid=os.getpid()))
  with cf.ProcessPoolExecutor(max_workers=6,initializer=init_worker,initargs=(str(OUT),)) as pool:
   for r in pool.map(functools.partial(a.run,horizon=10800,junction_checks=True),[(m,s) for m in ['south_drain','free_departure'] for s in [8101,8102,8103]]):print(r,flush=True)
  a.save(OUT/'status.json',dict(stage='complete'))
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

"""Fixed 15,000 vehicles/hour HV diagnostics and validation."""
import argparse,concurrent.futures,functools,json,os,shutil,subprocess
from pathlib import Path
import xml.etree.ElementTree as E
from utils import hv_flow_audit as a
from utils.hv_flow_repair import init_worker
from utils.hv_measured_traffic import allocate
ROOT=Path(__file__).resolve().parents[1]

def prepare(out,mode,duration,north400=False,entryprep=False):
 d=out/'inputs'/mode;d.mkdir(parents=True,exist_ok=True)
 for n in ('network.net.xml','highway.rou.xml','run.sumocfg'):shutil.copy2(ROOT/'scenarios/hv_stable'/n,d/n)
 if north400:
  from utils.extend_north_entry import extend
  a.save(d/'north-extension.json',extend(ROOT/'scenarios/hv_stable/network.net.xml',d/'network.net.xml'))
 if entryprep:
  assert not north400
  from utils.extend_entry_preparation import apply_extensions
  a.save(d/'entry-audit.json',apply_extensions(ROOT/'scenarios/hv_stable/network.net.xml',d/'network.net.xml'))
 tree=E.parse(d/'highway.rou.xml');flows=tree.findall('flow')
 rates=allocate(15000,[float(f.get('vehsPerHour')) for f in flows])
 if mode=='mainline_high':
  rates=[int(float(f.get('vehsPerHour'))) for f in flows]
  for i,f in enumerate(flows):
   rates[i]+={'route_06':3600,'route_16':1200}.get(f.get('route'),0)
 if mode in ('balanced','balanced_ramp_speed10'):
  byid={f.get('route'):i for i,f in enumerate(flows)}
  for src,dst,target in [('route_01','route_02',300),('route_07','route_08',1000),('route_03','route_06',600),('route_04','route_06',600),('route_05','route_06',600)]:
   i,j=byid[src],byid[dst];rates[j]+=rates[i]-target;rates[i]=target
 assert sum(rates)==15000
 counts=allocate(round(15000*duration/3600),rates)
 for f,rate,count in zip(flows,rates,counts):
  f.attrib.pop('vehsPerHour');f.set('number',str(count));f.set('begin','0');f.set('end',str(duration))
  if mode=='speed10' or (mode in ('ramp_speed10','free_ramp_speed10','balanced_ramp_speed10') and f.get('route') in ('route_03','route_04','route_05')):f.set('departSpeed','10')
  if mode in ('free','free_ramp_speed10'):f.set('departLane','free')
 tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
 a.save(d/'manifest.json',dict(mode=mode,north400=north400,entryprep=entryprep,total_vph=15000,duration=duration,planned=sum(counts),rates={f.get('route'):v for f,v in zip(flows,rates)},changes={'baseline':'proportional demand scaling only','speed10':'all flows departSpeed=10','ramp_speed10':'route03/04/05 departSpeed=10 only','free':'departLane=free only','free_ramp_speed10':'departLane=free plus route03/04/05 departSpeed=10','balanced':'entry totals unchanged; exit01=300,07=1000,03/04/05=600 each; remainder to alternate exits','balanced_ramp_speed10':'balanced exit allocation plus route03/04/05 departSpeed=10','mainline_high':'stable10200 + route06 3600 + route16 1200; local and ramp demand unchanged'}[mode],commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files={n:a.sha(d/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')},code_hashes={n:a.sha(ROOT/'utils'/n) for n in ('hv_high_traffic.py','hv_flow_audit.py')}))

def main():
 p=argparse.ArgumentParser();p.add_argument('--modes',nargs='+',default=['baseline']);p.add_argument('--seeds',nargs='+',type=int,default=[7101,7102,7103]);p.add_argument('--duration',type=int,default=3600);p.add_argument('--horizon',type=int,default=7200);p.add_argument('--output',default='results/hv_high15000_v1');p.add_argument('--north400',action='store_true');p.add_argument('--entryprep',action='store_true');args=p.parse_args()
 assert set(args.modes)<= {'baseline','speed10','ramp_speed10','free','free_ramp_speed10','balanced','balanced_ramp_speed10','mainline_high'}
 out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True);lock=out/'active.lock'
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  for mode in args.modes:prepare(out,mode,args.duration,args.north400,args.entryprep)
  a.save(out/'status.json',dict(stage='running',pid=os.getpid(),seeds=args.seeds,modes=args.modes))
  with concurrent.futures.ProcessPoolExecutor(max_workers=6,initializer=init_worker,initargs=(str(out),)) as pool:
   futures=[pool.submit(functools.partial(a.run,horizon=args.horizon,junction_checks=True),(m,s)) for m in args.modes for s in args.seeds]
   for f in concurrent.futures.as_completed(futures):print(f.result(),flush=True)
  a.save(out/'status.json',dict(stage='complete'))
 except Exception as exc:a.save(out/'status.json',dict(stage='error',error=repr(exc)));raise
 finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

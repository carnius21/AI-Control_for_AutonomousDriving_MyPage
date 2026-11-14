"""HV sensitivity tests from public counts, not a calibrated historical replay."""
import concurrent.futures
import csv
import functools
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from utils import hv_flow_audit as audit
from utils.hv_flow_repair import init_worker
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/hv_measured_20261113_exact'
DATA = ROOT/'docs/experiments/road-hourly-20251016.csv'

def extract():
    rows=[]
    for side in ('south','north'):
        path=ROOT/f'results/road_research_20261113/hour-{side}.xml'
        for r in ET.fromstring(path.read_bytes().decode('euc-kr')):
            c=[x.text for x in r]
            counts=[int(x) for x in c[10:22]]
            assert sum(counts)==int(c[22])
            rows.append(dict(station=c[2],start=c[3],end=c[4],date='-'.join(c[5:8]),hour_label=int(c[8]),direction_code=int(c[9]),total=int(c[22]),**{f'class_{i+1}':v for i,v in enumerate(counts)},source_sha256=audit.sha(path)))
    assert len(rows)==96
    for station,total in [('10010',193127),('10031',120134)]:
        subset=[r for r in rows if r['station']==station]
        assert len({(r['hour_label'],r['direction_code']) for r in subset})==48
        assert sum(r['total'] for r in subset)==total
    DATA.parent.mkdir(parents=True,exist_ok=True)
    with DATA.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return rows

def allocate(total, weights):
    raw=[total*w/sum(weights) for w in weights]
    result=[int(v) for v in raw]
    for i in sorted(range(len(raw)),key=lambda i:raw[i]-result[i],reverse=True)[:total-sum(result)]:result[i]+=1
    assert sum(result)==total
    return result

def prepare(rows):
    cases=[]
    for period,hours in [('night',[2,3]),('morning',[7,8,9]),('evening',[16,17,18])]:
        for bound,op in [('low',min),('high',max)]:
            mode=f'{period}_{bound}';cases.append(mode)
            d=OUT/'inputs'/mode;d.mkdir(parents=True,exist_ok=True)
            for name in ('network.net.xml','highway.rou.xml','run.sumocfg'):
                shutil.copy2(ROOT/'scenarios/hv_stable'/name,d/name)
            tree=ET.parse(d/'highway.rou.xml');rates={}
            measured={}
            for station,ids,weights in [('10010',range(3,7),[450,450,450,1050]),('10031',range(13,17),[200,200,200,2400])]:
                values=[r['total'] for r in rows if r['station']==station and r['hour_label'] in hours]
                measured[station]=op(values)
                rates.update({f'route_{i:02d}':n for i,n in zip(ids,allocate(op(values),weights))})
            for flow in tree.findall('flow'):
                flow.set('begin','0');flow.set('end','3600')
                if flow.get('route') in rates:flow.set('vehsPerHour',str(rates[flow.get('route')]))
                flow.set('number',str(int(float(flow.attrib.pop('vehsPerHour')))))
            tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
            audit.save(d/'manifest.json',dict(mode=mode,source_hour_labels=hours,bound=bound,station_directional_envelope=measured,
                assumptions=['Direction codes unresolved: use envelope across both directions, not an actual simultaneous observation.',
                'Hour labels differ 0-23 vs 1-24: use broad source-label bands, not aligned hourly replay.',
                'South station proxies route03-06 input; north station proxies route13-16 input.',
                'Existing turning shares, local-road inflow 4800/h and passenger/bus composition retained; trucks not reproduced.',
                'Counts measure passed vehicles, not latent demand. No field congestion calibration.'],
                total_vph=sum(int(f.get('number')) for f in tree.findall('flow')),
                commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                files={n:audit.sha(d/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')},
                source_csv_sha256=audit.sha(DATA),script_sha256=audit.sha(Path(__file__))))
    return cases

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'active.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        cases=prepare(extract())
        audit.save(OUT/'status.json',dict(stage='running',pid=os.getpid(),cases=cases,seeds=[6101,6102,6103]))
        with concurrent.futures.ProcessPoolExecutor(max_workers=6,initializer=init_worker,initargs=(str(OUT),)) as pool:
            for result in pool.map(functools.partial(audit.run,horizon=7200,junction_checks=True),[(m,s) for m in cases for s in (6101,6102,6103)]):print(result,flush=True)
        audit.save(OUT/'status.json',dict(stage='complete'))
    except Exception as exc:
        audit.save(OUT/'status.json',dict(stage='error',error=repr(exc)));raise
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()

"""Observed mainline envelope + explicitly assumed OD sensitivity, not replay."""
import argparse
import concurrent.futures as cf
import csv
import functools
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as E
from utils import hv_flow_audit as a
from utils.hv_flow_repair import init_worker
from utils.hv_measured_traffic import allocate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/hv_observed_bounds_20261113'
RAW = ROOT / 'results/road_research_v2_20261113'
DOC = ROOT / 'docs/experiments'
SEEDS = [9101, 9102, 9103]
HORIZON = 10800


def prepare():
    observations = {}
    quality = []
    for p in sorted(RAW.glob('hour-*.xml')):
        rows = [[x.text for x in r] for r in E.fromstring(p.read_bytes().decode('euc-kr'))]
        keys = [(tuple(r[5:10])) for r in rows]
        quality.append(dict(file=p.name,rows=len(rows),unique_date_hour_direction=len(set(keys)),sha256=a.sha(p)))
        if p.stem in ('hour-10010','hour-10031'):
            assert len(rows) == len(set(keys)) == 48
            assert all(sum(int(v) for v in r[10:22]) == int(r[22]) for r in rows)
            observations[p.stem[5:]] = [int(r[22]) for r in rows if int(r[8]) in (17,18)]
    modes=[]
    for bound, op in [('low',min),('high',max)]:
        for share in (10,25,40):
            mode=f'{bound}_exit{share}'; modes.append(mode)
            d=OUT/'inputs'/mode; d.mkdir(parents=True,exist_ok=True)
            assert not list((OUT/'runs').glob(f'{mode}-*/progress.json')), 'Inputs already used; do not overwrite'
            for n in ('network.net.xml','highway.rou.xml','run.sumocfg'):
                shutil.copy2(ROOT/'scenarios/hv_high15000_entryprep'/n,d/n)
            tree=E.parse(d/'highway.rou.xml'); rates={}
            for station,ids in [('10010',range(3,7)),('10031',range(13,17))]:
                rates.update({f'route_{i:02d}':v for i,v in zip(ids,allocate(op(observations[station]),[share,share,share,3*(100-share)]))})
            for f in tree.findall('flow'):
                if f.get('route') in rates: f.set('number',str(rates[f.get('route')]))
            assert not tree.findall('vehicle')
            tree.write(d/'highway.rou.xml',encoding='utf8',xml_declaration=True)
            a.save(d/'manifest.json',dict(mode=mode,mainline_bound=bound,exit_share_assumed=share/100,
                mainline_station_proxies={k:op(v) for k,v in observations.items()},
                local_total_assumed=4800,route_counts={f.get('route'):int(f.get('number')) for f in tree.findall('flow')},
                limitations=['Not a measured OD replay. Direction mapping and hour labels unresolved.',
                'Source label 17/18, both directions envelope; extrema need not be simultaneous.',
                'Local 4800/h unchanged assumption. Three ramp destinations equally split by assumption.',
                'No ramp counts downloaded; national-road ambiguous rows excluded.',
                'Bus 5%, passenger violators 2%, controller mix unchanged assumptions; truck classes not reproduced.'],
                files={n:a.sha(d/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')}))
    a.save(OUT/'design.json',dict(cases=modes,seeds=SEEDS,horizon=HORIZON,source_quality=quality,
        prepared_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    shutil.copy2(OUT/'design.json',DOC/'ic-observed-bounds-design-20261113.json')
    with (DOC/'ic-observed-bounds-inputs-20261113.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['case','route','vehicles_in_3600s','provenance'])
        for m in modes:
            for r,n in json.loads((OUT/'inputs'/m/'manifest.json').read_text())['route_counts'].items():
                w.writerow([m,r,n,'observed_mainline_envelope_x_assumed_turn_share' if int(r[-2:]) in list(range(3,7))+list(range(13,17)) else 'unmeasured_existing_local_assumption'])
    print(json.dumps({'cases':modes,'source_quality':quality},ensure_ascii=False))


def run():
    design=json.loads((OUT/'design.json').read_text())
    for m in design['cases']:
        d=OUT/'inputs'/m
        for n,h in json.loads((d/'manifest.json').read_text())['files'].items(): assert a.sha(d/n)==h
    lock=OUT/'active.lock'; fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        a.save(OUT/'status.json',dict(stage='running',pid=os.getpid(),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
        with cf.ProcessPoolExecutor(max_workers=6,initializer=init_worker,initargs=(str(OUT),)) as pool:
            jobs=[pool.submit(functools.partial(a.run,horizon=HORIZON,junction_checks=True),(m,s)) for m in design['cases'] for s in SEEDS]
            for job in cf.as_completed(jobs):print(job.result(),flush=True)
        a.save(OUT/'status.json',dict(stage='complete'))
    except Exception as exc:
        a.save(OUT/'status.json',dict(stage='error',error=repr(exc)));raise
    finally:lock.unlink(missing_ok=True)


def summarize():
    rows=[]; detail=[]
    for p in sorted((OUT/'runs').glob('*/complete.json')):
        r=json.loads(p.read_text());rs=list(r['routes'].values());n=sum(x['arrived'] for x in rs)
        samples=json.loads((p.parent/'samples.json').read_text())
        rows.append(dict(case=r['mode'],seed=r['seed'],planned=sum(x['planned'] for x in rs),arrived=n,
            collisions=r['collisions'],teleports=r['teleports'],pending=len(r['pending']),active=len(r['leftovers']),
            ended=r['ended'],mean_depart_delay=sum(x['mean_depart_delay']*x['arrived'] for x in rs)/max(1,n),
            mean_trip_duration=sum(x['mean_duration']*x['arrived'] for x in rs)/max(1,n),
            peak_pending=max(x['pending'] for x in samples),
            emergency_braking_warnings=(p.parent/'sumo.log').read_text(errors='replace').count('performs emergency braking'),
            passed=r['passed'],run=str(p.parent.relative_to(ROOT))))
        detail.extend(dict(case=r['mode'],seed=r['seed'],route=k,**v) for k,v in r['routes'].items())
    for suffix,data in [('results',rows),('routes',detail)]:
        if data:
            with (DOC/f'ic-observed-bounds-{suffix}-20261113.csv').open('w',newline='',encoding='utf8') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    for m in sorted({r['case'] for r in rows}):
        g=[r for r in rows if r['case']==m]
        print(m, 'n',len(g),'pass',sum(r['passed'] for r in g),'arrived',sum(r['arrived'] for r in g),
              'collision',sum(r['collisions'] for r in g),'pending',sum(r['pending'] for r in g),
              'delay',round(min(r['mean_depart_delay'] for r in g),1),round(max(r['mean_depart_delay'] for r in g),1))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summarize']);args=p.parse_args()
    globals()[args.action]()

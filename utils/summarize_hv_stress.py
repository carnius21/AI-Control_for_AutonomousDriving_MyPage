"""Summarize immutable HV stress outputs; raw runs stay local."""
import csv,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 out=ROOT/'results/hv_entryprep_stress_20261113';rows=[];details=[]
 for p in sorted((out/'runs').glob('*/complete.json')):
  r=json.loads(p.read_text());samples=json.loads((p.parent/'samples.json').read_text());rs=list(r['routes'].values());n=sum(x['arrived'] for x in rs)
  log=(p.parent/'sumo.log').read_text(errors='replace')
  row=dict(mode=r['mode'],seed=r['seed'],planned=sum(x['planned'] for x in rs),arrived=n,colliding_vehicle_events=r['collisions'],teleports=r['teleports'],pending=len(r['pending']),leftovers=len(r['leftovers']),ended=r['ended'],mean_depart_delay=sum(x['mean_depart_delay']*x['arrived'] for x in rs)/max(1,n),max_depart_delay=max(x['max_depart_delay'] for x in rs),peak_pending=max(x['pending'] for x in samples),peak_stopped=max(x['stopped'] for x in samples),emergency_braking_warnings=log.count('performs emergency braking'),passed=r['passed'],run=str(p.parent.relative_to(ROOT)))
  rows.append(row)
  details.append(dict(mode=r['mode'],seed=r['seed'],routes=r['routes'],stop_locations=r['stop_locations'],leftovers=r['leftovers'],collision_log=[x for x in log.splitlines() if 'collision' in x.lower()]))
 if not rows:return
 target=ROOT/'docs/experiments/ic-hv-stress-20261113.csv'
 with target.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (out/'analysis.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
 for mode in dict.fromkeys(x['mode'] for x in rows):
  group=[r for r in rows if r['mode']==mode]
  print(mode,len(group),'pass',sum(x['passed'] for x in group),'arrived',sum(x['arrived'] for x in group),'collision',sum(x['colliding_vehicle_events'] for x in group),'pending',sum(x['pending'] for x in group),'left',sum(x['leftovers'] for x in group),'delay',round(min(x['mean_depart_delay'] for x in group),1),round(max(x['mean_depart_delay'] for x in group),1),'peakpending',max(x['peak_pending'] for x in group),'ended',max(x['ended'] for x in group))
if __name__=='__main__':main()

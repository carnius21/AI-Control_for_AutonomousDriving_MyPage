"""Boundary-only entry preparation: north +300m, short other approaches >400m."""
import collections,heapq,json,shutil
from pathlib import Path
import xml.etree.ElementTree as E
from utils.extend_north_entry import extend,ROOT
from utils.hv_flow_audit import save,sha
EXTENSIONS={'86198728':300,'169728849':100,'52873356':100,'544295537':100,'781184662#1':250}
LABELS={'86198728':'북쪽 남행 · 13–16번','169728849':'동쪽 진입로 · 01–02번','52873356':'남쪽 북행 · 03–06번','544295537':'동쪽 본선 · 07–08번','781184662#1':'서쪽 진입 · 10–12번','556956812#1':'동쪽 직진 · 09번'}
def audit_entries(network):
 n=E.parse(network);edges={e.get('id'):e for e in n.findall('edge')};lanes={l.get('id'):l for e in edges.values() for l in e.findall('lane')};links=collections.defaultdict(dict)
 for c in n.findall('connection'):
  if c.get('from','').startswith(':'):continue
  via=c.get('via');length=float(lanes[via].get('length')) if via in lanes else 0
  links[c.get('from')][c.get('to')]=min(links[c.get('from')].get(c.get('to'),1e9),length)
 result=[]
 for start in LABELS:
  q=[(0,start,[])];seen=set()
  while q:
   dist,eid,path=heapq.heappop(q)
   if eid in seen:continue
   seen.add(eid);ls=edges[eid].findall('lane');dist+=min(float(l.get('length')) for l in ls);path=path+[eid]
   if len(links[eid])>1 or not links[eid]:
    result.append(dict(entry=start,label=LABELS[start],has_fork=len(links[eid])>1,distance=round(dist,2),path=path,fork_edge=eid,entry_lanes=len(edges[start].findall('lane'))));break
   for target,gap in links[eid].items():heapq.heappush(q,(dist+gap,target,path))
 return result

def apply_extensions(source,target):
 before=audit_entries(source);source_hash=sha(source);changes=[]
 for i,(eid,length) in enumerate(EXTENSIONS.items()):changes.append(extend(source if i==0 else target,target,length,edge_id=eid))
 after=audit_entries(target)
 for old,new in zip(before,after):
  assert old['path']==new['path'] and old['has_fork']==new['has_fork']
  assert abs(new['distance']-old['distance']-EXTENSIONS.get(old['entry'],0))<.01
  if new['has_fork']:assert new['distance']>400
 return dict(source_sha256=source_hash,network_sha256=sha(target),extensions=EXTENSIONS,before=before,after=after,changes=changes,metric='Conservative shortest lane length + minimum internal connector length to first outgoing-edge fork. Not all of this is usable lane-change space.',single_lane_caveat='01/02 approach has one lane; merge-to-fork edge169929488#0 remains67.40m.')

def main():
 src=ROOT/'maps/toegyewon_only';dst=ROOT/'maps/toegyewon_entryprep'
 if dst.exists():raise FileExistsError(dst)
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('scenery.add.xml','building-display-audit.json','marking-comparison.json'))
 for name in ('network.net.xml','landscaped.net.xml'):save(dst/(name+'.entry-audit.json'),apply_extensions(src/name,dst/name))
 cfg=E.parse(dst/'landscape.sumocfg');cfg.find('input/additional-files').set('value','../toegyewon_only/scenery.add.xml');cfg.write(dst/'landscape.sumocfg',encoding='utf8',xml_declaration=True)
 bounds=[float(x) for x in E.parse(dst/'network.net.xml').find('location').get('convBoundary').split(',')]
 for name in ('view.xml','landscape-view.xml'):
  t=E.parse(dst/name);v=t.find('viewport');v.set('x',str((bounds[0]+bounds[2])/2));v.set('y',str((bounds[1]+bounds[3])/2));v.set('zoom','105');t.write(dst/name,encoding='utf8',xml_declaration=True)
 m=json.loads((dst/'manifest.json').read_text());m['network_sha256']=sha(dst/'network.net.xml');m['bounds']=bounds;m['entry_extensions_m']=EXTENSIONS;save(dst/'manifest.json',m)
 src=ROOT/'scenarios/hv_high15000';dst=ROOT/'scenarios/hv_high15000_entryprep';dst.mkdir(parents=True,exist_ok=False)
 for name in ('highway.rou.xml','run.sumocfg'):shutil.copy2(src/name,dst/name)
 report=apply_extensions(src/'network.net.xml',dst/'network.net.xml');save(dst/'entry-audit.json',report)
 save(dst/'manifest.json',dict(source_profile='hv_high15000',total_vph=15000,entry_extensions_m=EXTENSIONS,files={n:sha(dst/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')}))
 print(json.dumps(report['before'],ensure_ascii=False));print(json.dumps(report['after'],ensure_ascii=False))
if __name__=='__main__':main()

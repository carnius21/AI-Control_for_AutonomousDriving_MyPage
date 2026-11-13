"""Crop a separate SUMO network without rebuilding surviving junction geometry."""
import copy, json, hashlib, math, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'maps/toegyewon_osm'
DEST=ROOT/'maps/toegyewon_only'
BOX=(1320.,600.,2050.,1750.)
def points(s):return [tuple(map(float,p.split(','))) for p in s.split()]
def shape(ps):return ' '.join(','.join(f'{v:.2f}' for v in p) for p in ps)
def inside(p):return BOX[0]<=p[0]<=BOX[2] and BOX[1]<=p[1]<=BOX[3]
def clip(ps):
 out=[]
 for a,b in zip(ps,ps[1:]):
  dx,dy=b[0]-a[0],b[1]-a[1];lo,hi=0.,1.
  for p,q in [(-dx,a[0]-BOX[0]),(dx,BOX[2]-a[0]),(-dy,a[1]-BOX[1]),(dy,BOX[3]-a[1])]:
   if p==0:
    if q<0:hi=-1;break
   elif p<0:lo=max(lo,q/p)
   else:hi=min(hi,q/p)
  if lo<=hi:
   for t in (lo,hi):
    c=(a[0]+dx*t,a[1]+dy*t)
    if not out or math.dist(out[-1],c)>.001:out.append(c)
 return out

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 original=(SOURCE/'network.net.xml').read_bytes();r=ET.fromstring(original)
 external={e.get('id'):e for e in r.findall('edge') if not e.get('function')}
 kept={};boundaries=[];valid_nodes=set()
 for eid,e in external.items():
  lanes=e.findall('lane');cropped=[clip(points(l.get('shape'))) for l in lanes]
  if any(len(p)<2 for p in cropped):continue
  for lane,ps in zip(lanes,cropped):
   old=points(lane.get('shape'))
   if not inside(old[0]) or not inside(old[-1]):
    lane.set('shape',shape(ps));lane.set('length',str(round(sum(math.dist(a,b) for a,b in zip(ps,ps[1:])),2)))
  ps=points(e.get('shape',lanes[0].get('shape')))
  clipped=clip(ps)
  if len(clipped)>1:e.set('shape',shape(clipped))
  for attr,index in [('from',0),('to',-1)]:
   oldnode=next(j for j in r.findall('junction') if j.get('id')==e.get(attr))
   if not inside((float(oldnode.get('x')),float(oldnode.get('y')))):
    nid=f'cut_{eid}_{attr}';e.set(attr,nid)
    xy=tuple(sum(p[index][k] for p in cropped)/len(cropped) for k in (0,1))
    j=ET.Element('junction',id=nid,type='dead_end',x=str(xy[0]),y=str(xy[1]),incLanes=' '.join(l.get('id') for l in lanes) if attr=='to' else '',intLanes='',shape=shape([xy]))
    boundaries.append(j)
   else:valid_nodes.add(e.get(attr))
  kept[eid]=e
 internal={e.get('id'):e for e in r.findall('edge') if e.get('function')=='internal' and any(e.get('id').startswith(':'+n+'_') for n in valid_nodes)}
 valid_edges=set(kept)|set(internal)
 valid_lanes={l.get('id') for e in list(kept.values())+list(internal.values()) for l in e.findall('lane')}
 for el in list(r):
  if el.tag=='edge' and el.get('id') not in valid_edges:r.remove(el)
  elif el.tag=='junction':
   if el.get('id') not in valid_nodes and not any(el.get('id').startswith(':'+n+'_') for n in valid_nodes):r.remove(el)
   else:
    for attr in ('incLanes','intLanes'):el.set(attr,' '.join(x for x in el.get(attr,'').split() if x in valid_lanes))
  elif el.tag=='connection' and (el.get('from') not in valid_edges or el.get('to') not in valid_edges):r.remove(el)
 for j in boundaries:r.append(j)
 r.find('location').set('convBoundary',','.join(map(str,BOX)))
 ET.ElementTree(r).write(DEST/'network.net.xml',encoding='utf-8',xml_declaration=True)
 links={e:set() for e in kept};incoming={e:set() for e in kept}
 for c in r.findall('connection'):
  a,b=c.get('from'),c.get('to')
  if a in kept and b in kept:links[a].add(b);incoming[b].add(a)
 starts=sorted(e for e in kept if not incoming[e]);ends={e for e in kept if not links[e]}
 paths=[]
 def visit(path):
  if path[-1] in ends:paths.append(path);return
  for nxt in sorted(links[path[-1]]):
   if nxt not in path:visit(path+[nxt])
 for start in starts:visit([start])
 routes={f'route_{i:02d}':p for i,p in enumerate(paths,1)}
 rr=ET.Element('routes')
 old=ET.parse(ROOT/'results/ic_campaign_v2/maps/base/highway.rou.xml').getroot()
 for v in old.findall('vType'):rr.append(copy.deepcopy(v))
 for name,path in routes.items():ET.SubElement(rr,'route',id=name,edges=' '.join(path))
 ET.ElementTree(rr).write(DEST/'routes.rou.xml',encoding='utf-8',xml_declaration=True)
 cfg=ET.Element('configuration');inp=ET.SubElement(cfg,'input')
 ET.SubElement(inp,'net-file',value='network.net.xml');ET.SubElement(inp,'route-files',value='routes.rou.xml')
 proc=ET.SubElement(cfg,'processing');ET.SubElement(proc,'time-to-teleport',value='-1')
 gui=ET.SubElement(cfg,'gui_only');ET.SubElement(gui,'gui-settings-file',value='view.xml')
 ET.ElementTree(cfg).write(DEST/'review.sumocfg',encoding='utf-8',xml_declaration=True)
 shutil.copy2(SOURCE/'view.xml',DEST/'view.xml')
 report=dict(source_sha256=hashlib.sha256(original).hexdigest(),network_sha256=hashlib.sha256((DEST/'network.net.xml').read_bytes()).hexdigest(),bounds=BOX,edges=len(kept),entries=starts,exits=sorted(ends),routes=routes,definition='All edge-simple directed entry-to-exit paths; repeated-edge loops excluded')
 (DEST/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 assert (SOURCE/'network.net.xml').read_bytes()==original
 print(json.dumps({k:v for k,v in report.items() if k!='routes'},indent=2));print('Routes',len(routes))
if __name__=='__main__':main()

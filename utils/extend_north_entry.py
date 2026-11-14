"""Extend only the north-to-south entry by 400 m without rebuilding junctions."""
import copy,json,math,shutil
from pathlib import Path
import xml.etree.ElementTree as E
from utils.hv_flow_audit import sha,save
ROOT=Path(__file__).resolve().parents[1]
EDGE='86198728'
def points(s):return [[float(v) for v in token.split(',')] for token in s.split()]
def fmt(p):return ','.join(f'{v:.3f}' for v in p)
def extend(source,target,distance=400,edge_id=EDGE):
 tree=E.parse(source);root=tree.getroot();before=copy.deepcopy(root)
 edge=root.find(f"edge[@id='{edge_id}']");node_id=edge.get('from');node=root.find(f"junction[@id='{node_id}']")
 assert node.get('type')=='dead_end' and not node.get('incLanes')
 assert len([e for e in root.findall('edge') if e.get('from')==node_id or e.get('to')==node_id])==1
 ps=points(edge.get('shape'));dx,dy=ps[0][0]-ps[1][0],ps[0][1]-ps[1][1];norm=math.hypot(dx,dy);dx*=distance/norm;dy*=distance/norm
 def prepend(s):
  first=points(s)[0];new=first.copy();new[0]+=dx;new[1]+=dy
  return fmt(new)+' '+s
 old_lengths={l.get('id'):float(l.get('length')) for l in edge.findall('lane')}
 edge.set('shape',prepend(edge.get('shape')))
 for lane in edge.findall('lane'):
  lane.set('shape',prepend(lane.get('shape')));lane.set('length',f"{float(lane.get('length'))+distance:.2f}")
 node.set('x',f"{float(node.get('x'))+dx:.3f}");node.set('y',f"{float(node.get('y'))+dy:.3f}")
 moved=points(node.get('shape'))
 for p in moved:p[0]+=dx;p[1]+=dy
 node.set('shape',' '.join(fmt(p) for p in moved))
 loc=root.find('location');bounds=[float(x) for x in loc.get('convBoundary').split(',')]
 newpoints=[points(l.get('shape'))[0] for l in edge.findall('lane')]+moved
 loc.set('convBoundary',','.join(map(str,[min(bounds[0],min(p[0] for p in newpoints)-5),min(bounds[1],min(p[1] for p in newpoints)-5),max(bounds[2],max(p[0] for p in newpoints)+5),max(bounds[3],max(p[1] for p in newpoints)+5)])))
 # Every other edge (including internal lanes), junction and connection stays identical.
 for old,new in zip(before,root):
  if old.tag=='location' or (old.tag=='edge' and old.get('id')==edge_id) or (old.tag=='junction' and old.get('id')==node_id):continue
  assert E.tostring(old)==E.tostring(new),(old.tag,old.get('id'))
 old_edge=before.find(f"edge[@id='{edge_id}']")
 for old,new in zip(old_edge.findall('lane'),edge.findall('lane')):
  assert new.get('shape').split()[1:]==old.get('shape').split()
  assert {k:v for k,v in old.attrib.items() if k not in ('shape','length')}=={k:v for k,v in new.attrib.items() if k not in ('shape','length')}
  q=points(new.get('shape'));assert abs(math.dist(q[0][:2],q[1][:2])-distance)<.002
 target.parent.mkdir(parents=True,exist_ok=True);tree.write(target,encoding='utf8',xml_declaration=True)
 report=dict(edge=edge_id,entry_node=node_id,extension_m=distance,lanes=len(old_lengths),old_lengths=old_lengths,new_lengths={l.get('id'):float(l.get('length')) for l in edge.findall('lane')},source=str(source),source_sha256=sha(source),output_sha256=sha(target),other_geometry_connections_permissions_unchanged=True,height='New segment retains original entry z; experimental extension, not surveyed elevation.')
 return report

def main():
 source=ROOT/'maps/toegyewon_only';dest=ROOT/'maps/toegyewon_north400'
 if dest.exists():raise FileExistsError('Preserve existing map; choose a fresh destination')
 shutil.copytree(source,dest,ignore=shutil.ignore_patterns('scenery.add.xml'))
 cfg=E.parse(dest/'landscape.sumocfg');cfg.find('input/additional-files').set('value','../toegyewon_only/scenery.add.xml');cfg.write(dest/'landscape.sumocfg',encoding='utf8',xml_declaration=True)
 for stale in ('building-display-audit.json','marking-comparison.json'):
  (dest/stale).unlink(missing_ok=True)
 reports=[]
 for filename in ('network.net.xml','landscaped.net.xml'):reports.append(extend(source/filename,dest/filename))
 save(dest/'north-extension.json',reports)
 for filename in ('view.xml','landscape-view.xml'):
  t=E.parse(dest/filename);v=t.find('viewport');v.set('x','1640');v.set('y','1335');v.set('zoom','115');t.write(dest/filename,encoding='utf8',xml_declaration=True)
 # Copied metadata describes the preserved source. Update explicit map hash and extension provenance.
 mp=dest/'manifest.json';m=json.loads(mp.read_text(encoding='utf8'));m['network_sha256']=sha(dest/'network.net.xml');m['north_extension']=reports[0];save(mp,m)
 src=ROOT/'scenarios/hv_high15000';dst=ROOT/'scenarios/hv_high15000_north400';dst.mkdir(parents=True,exist_ok=False)
 for filename in ('highway.rou.xml','run.sumocfg'):shutil.copy2(src/filename,dst/filename)
 report=extend(src/'network.net.xml',dst/'network.net.xml');save(dst/'north-extension.json',report)
 save(dst/'manifest.json',dict(source_profile='hv_high15000',total_vph=15000,geometry_extension=report,files={n:sha(dst/n) for n in ('network.net.xml','highway.rou.xml','run.sumocfg')}))
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()

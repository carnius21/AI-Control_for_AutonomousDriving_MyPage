"""Static source fidelity and route connectivity checks; no driving/learning experiment."""
import json,math,os,xml.etree.ElementTree as ET
os.environ['IC_LIBSUMO']='1'
from env.sumo_env import traci
from sumolib import checkBinary
import sumolib
from utils.rebuild_osm_map import DEST

def main():
 source=ET.parse(DEST/'source.osm').getroot();ways={w.get('id'):w for w in source.findall('way')};nodes={n.get('id'):(float(n.get('lon')),float(n.get('lat'))) for n in source.findall('node')}
 root=ET.parse(DEST/'network.net.xml').getroot();junctions={j.get('id'):j for j in root.findall('junction')};edges={e.get('id'):e for e in root.findall('edge') if e.get('function')!='internal'}
 scope=json.loads((DEST/'scope.json').read_text(encoding='utf8'))
 assert set(edges)==set(scope['edges'])|{'86198708#1','844484877#1','170059993#1','206426298#1'}, 'Unexpected missing or extra scope edges'
 audit=json.loads((DEST/'import-audit.json').read_text(encoding='utf8'));lane_checks=0
 for row in audit['edges']:
  if row['oneway']=='yes' and row['osm_lanes'] and row['osm_lanes'].isdigit() and not row.get('lane_override'):
   assert row['lanes']==int(row['osm_lanes']),row
   lane_checks+=1
 for wid,count in [('86198728',5),('52873356',4),('37927512',3),('170059994',4)]:
  found=[e for k,e in edges.items() if k.split('#')[0]==wid];assert found and all(len(e.findall('lane'))==count for e in found)
 overrides=json.loads((DEST/'lane-overrides.json').read_text(encoding='utf8'))
 for eid,item in overrides.items():assert len(edges[eid].findall('lane'))==item['num_lanes'],eid
 assert edges['169929488#0'].get('from')=='1808903166'
 assert edges['544292616'].get('to')==edges['844484877'].get('from')=='1000493465'
 assert not any(c.get('from')=='86198728' and c.get('to','').startswith('169929488') for c in root.findall('connection'))
 # Audit raw centerlines against OSM nodes. SUMO overlap avoidance can shift endpoints; report rather than conceal these deviations.
 max_error=0.;checked=0;cache={};deviations=[];intentional_changes=[]
 adjustments=json.loads((DEST/'layout-adjustments.json').read_text(encoding='utf8'))
 traci.start([checkBinary('sumo'),'-c',str(DEST/'review.sumocfg'),'--no-step-log','true'])
 try:
  for eid,e in edges.items():
   wid=eid.lstrip('-').split('#')[0];w=ways[wid]
   if wid not in cache:cache[wid]=[traci.simulation.convertGeo(*nodes[n.get('ref')],fromGeo=True) for n in w.findall('nd')]
   if e.get('shape'):points=[tuple(map(float,p.split(',')[:2])) for p in e.get('shape').split()]
   else:points=[(float(junctions[e.get(side)].get('x')),float(junctions[e.get(side)].get('y'))) for side in ('from','to')]
   if eid=='86198725':
    expected=[tuple(map(float,p.split(','))) for p in adjustments['junction_smoothing']['86198725'].split()]
    assert all(sumolib.geomhelper.distancePointToPolygon(p,expected)<1.7 for p in points)
    intentional_changes.append(dict(edge=eid,reason='Southbound four-lane continuation after exclusive ramp fork'))
    continue
   if eid in adjustments.get('junction_smoothing',{}):
    expected=[tuple(map(float,p.split(','))) for p in adjustments['junction_smoothing'][eid].split()]
    assert math.dist(points[0],expected[0])<.02 and math.dist(points[-1],expected[-1])<.02,('aligned endpoints',eid)
    assert all(sumolib.geomhelper.distancePointToPolygon(p,expected)<.03 for p in points),('aligned shape mismatch',eid)
    assert all(sumolib.geomhelper.distancePointToPolygon(p,points)<.03 for p in expected),('aligned shape simplification',eid)
    intentional_changes.append(dict(edge=eid,reason='Reviewed local junction tangent/lane-group alignment'))
    continue
   if eid in ('86198708','86198708#1'):
    expected=[tuple(map(float,p.split(','))) for p in adjustments['north_boundary_edges']['86198708'].split()]
    for p in points:
     assert sumolib.geomhelper.distancePointToPolygon(p,expected)<1.7,('north offset corridor',eid,p)
    intentional_changes.append(dict(edge=eid,reason='Auxiliary lane axis and split before north merge'))
    continue
   if eid==adjustments['north_merge']['edge'] or eid in adjustments.get('north_boundary_edges',{}):
    expected_shape=adjustments['north_merge']['shape'] if eid==adjustments['north_merge']['edge'] else adjustments['north_boundary_edges'][eid]
    expected=[tuple(map(float,p.split(','))) for p in expected_shape.split()]
    assert points==expected,'Shortened merge differs from approved adjustment'
    intentional_changes.append(dict(edge=eid,reason='User requested earlier merge, original OSM geometry intentionally changed'))
    continue
   for p in points:
    def segment_distance(a,b):
     dx=b[0]-a[0];dy=b[1]-a[1];length2=dx*dx+dy*dy
     t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length2)) if length2 else 0.
     return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    error=min(segment_distance(a,b) for a,b in zip(cache[wid],cache[wid][1:]));max_error=max(max_error,error)
    smooth=next(row for row in audit['edges'] if row['edge']==eid).get('geometry_rounding',False)
    tolerance=(4.05 if smooth else .05)+(1.65 if eid in {'844484877#1','170059993','170059993#1','206426298#1','844484878#1','86198722'} else 0)
    if error>tolerance:deviations.append(dict(edge=eid,error_m=error,point=p))
   checked+=1
 finally:traci.close()
 markings=json.loads((DEST/'markings.json').read_text(encoding='utf8'))
 for eid in markings['solid']:
  lanes=edges[eid].findall('lane')
  for i,lane in enumerate(lanes):
   if i<len(lanes)-1:assert lane.get('changeLeft')==markings['solid_allowed_classes'],lane.attrib
   if i>0:assert lane.get('changeRight')==markings['solid_allowed_classes'],lane.attrib
 for eid in markings['dashed']:
  assert all(l.get('changeLeft') is None and l.get('changeRight') is None for l in edges[eid].findall('lane')),eid
 connections={(c.get('from'),int(c.get('fromLane')),c.get('to'),int(c.get('toLane'))) for c in root.findall('connection')}
 # Five approach lanes split into four through lanes and one exclusive ramp lane.
 assert len(edges['86198725'].findall('lane'))==4
 expected={('86198728',i+1,'86198725',i) for i in range(4)}|{('86198728',0,'37927508',0)}
 assert {c for c in connections if c[0]=='86198728'}==expected
 assert '86198725.50' not in junctions
 # Northbound lower ramp: 4 + 1 -> 5, then 4 until the next merge.
 for eid,n in [('844484878#0',4),('844484878#1',5),('86198722',5),('86198708',5),('86198708#1',4)]:
  assert len(edges[eid].findall('lane'))==n,eid
 # Northern continuation must retain all four mainline lane axes.
 for i in range(4):
  points=[tuple(map(float,p.split(','))) for p in edges['86198708#1'].findall('lane')[i].get('shape').split()]
  q=tuple(map(float,edges['1414146971'].findall('lane')[i+1].get('shape').split()[0].split(',')))
  a,b=points[-2:];dx,dy=b[0]-a[0],b[1]-a[1]
  assert abs(dx*(q[1]-b[1])-dy*(q[0]-b[0]))/math.hypot(dx,dy)<.1,('north axis',i)
 assert len(edges['1414146971'].findall('lane'))==5
 assert ('280963368',0,'1414146971',0) in connections
 for i in range(4):assert ('86198708#1',i,'1414146971',i+1) in connections
 # Through lanes must not shift sideways by half a lane at the auxiliary drop.
 for i in range(4):
  incoming=[tuple(map(float,p.split(','))) for p in edges['86198708'].findall('lane')[i+1].get('shape').split()]
  outgoing=tuple(map(float,edges['86198708#1'].findall('lane')[i].get('shape').split()[0].split(',')))
  u,v=incoming[-2:];dx,dy=v[0]-u[0],v[1]-u[1]
  lateral=abs(dx*(outgoing[1]-v[1])-dy*(outgoing[0]-v[0]))/math.hypot(dx,dy)
  assert lateral<.25,('mainline alignment',i,lateral)
 assert len(edges['86198708#1'].findall('lane'))==4
 assert float(edges['86198708#1'].find('lane').get('length'))<55
 for i in range(4):assert ('86198708',i+1,'86198708#1',i) in connections
 assert ('37375274',0,'844484878#1',0) in connections
 for i in range(4):
  assert ('844484878#0',i,'844484878#1',i+1) in connections
  assert ('844484878#1',i+1,'86198722',i+1) in connections
  assert ('86198722',i,'86198708',i) in connections
 assert ('544293888#0',0,'37375274',0) in connections
 assert ('544293888#0',1,'544293888#1',0) in connections
 assert edges['280963368'].get('to')=='436249297'
 for nid in ('436249297','12994833426','436256826'):assert float(junctions[nid].get('y'))<=1700
 assert max(float(p.split(',')[1]) for p in edges['280963368'].get('shape').split())<=1683
 assert len(edges['170059993'].findall('lane'))==1
 assert len(edges['170059993#1'].findall('lane'))==2
 assert len(edges['781184662#3'].findall('lane'))==3
 for c in [('797789364',0,'781184662#3',0),('781184662#2',0,'781184662#3',1),('781184662#2',1,'781184662#3',2),('781184662#3',0,'169929484',0),('781184662#3',1,'169929497',0),('781184662#3',2,'169929497',1)]:assert c in connections,c
 # Keep all three lanes until the downstream physical fork.
 assert len(edges['169929488#0'].findall('lane'))==3
 assert math.hypot(float(junctions['1808903388'].get('x'))-1750.0,float(junctions['1808903388'].get('y'))-1610.0)<.02
 expected_fork={('169929488#0',0,'169728799',0),('169929488#0',1,'169929488#1',0),('169929488#0',2,'169929488#1',1)}
 assert {c for c in connections if c[0]=='169929488#0'}==expected_fork
 continuity=[('544295537','169929488#0',3),('169929488#1','1414146968',2),('1414146968','372821396',2),('1413342573','544295537',3),('169929478','169929482',2),('597119334','597119333',2),('841607184#0','841607184#1',2),('372821396','544292617',2),('544292617','544292616',2),('169728799','280963368',1),('170059993#1','544293888#0',2)]
 for before,after,count in continuity:
  for lane in range(count):assert (before,lane,after,lane) in connections,(before,after,lane)
 assert sum(float(edges[e].find('lane').get('length')) for e in ('170059989','170059989#1'))>250, 'Merge polygon swallowed the loop ramp'
 assert len(edges['37927509'].findall('lane'))==4
 assert len(edges['206426298'].findall('lane'))==5
 assert len(edges['206426298#1'].findall('lane'))==4
 assert len(edges['844484877#1'].findall('lane'))==4
 for lane in range(4):assert ('206426298#1',lane,'844484877',lane+1) in connections
 for lane in range(2):assert ('544292616',lane,'844484877',lane) in connections
 for lane in range(1,5):assert ('844484877',lane,'844484877#1',lane-1) in connections
 net=sumolib.net.readNet(str(DEST/'network.net.xml'))
 pairs=[('west_fork_to_north_mainline','169929488#0','1414146971'),('south_ramp_through_taper','169929488#1','844484877#1'),('south_to_east','86198728','1063527748'),('north_to_east','52873356','1063527748'),('north_to_west','52873356','170059992'),('outer_to_south','169929488#0','844484877'),('return_to_north','170059993','86198708'),('return_to_south','170059993','844484877'),('toegyewon_to_sano','86198728','169929482'),('sano_to_toegyewon','169929493','844484877'),('sano_north_to_south','596640907','72387791#1'),('sano_south_to_north','841607178#15','841607184#3')]
 paths={}
 for label,start,end in pairs:
  path,cost=net.getShortestPath(net.getEdge(start),net.getEdge(end),vClass='passenger')
  assert path,label
  paths[label]=dict(edges=[e.getID() for e in path],length_m=cost)
 report=dict(intentional_geometry_changes=intentional_changes,lane_continuity_checks=continuity,solid_edges_checked=len(markings['solid']),dashed_edges_checked=len(markings['dashed']),status='review_required' if deviations else 'passed',geometry_deviations=deviations,no_simulation_steps_or_training=True,source_geometry_edges_checked=checked,max_projected_source_error_m=max_error,explicit_oneway_lane_tag_checks=lane_checks,roads_with_unverified_lane_defaults=sum(r['lane_source'].startswith('SUMO') for r in audit['edges']),routes=paths,geometry_tolerances_m={'unchanged':0.05,'rounded_curves':4.05,'auxiliary_lane_drop_center_shift':1.65},limitations=['Lane-to-lane mapping and signals inferred by SUMO where OSM lacks detail','No measured road elevations; layer topology preserved without physical Z inference','Conversion warnings retained; no traffic-capacity or AV certification'])
 (DEST/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

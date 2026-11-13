"""Add actual OSM building footprints and illustrative bridge edges to the display copy."""
from pathlib import Path
import sys, json, xml.etree.ElementTree as E
sys.path.append('C:/Program Files (x86)/Eclipse/Sumo/tools')
import traci
from env.road_builder import shifted, shape

p=Path(__file__).resolve().parents[1]/'maps'/'toegyewon_only'
s=E.parse(p.parent/'toegyewon_osm'/'source.osm');nodes={n.get('id'):(float(n.get('lon')),float(n.get('lat'))) for n in s.findall('node')}
n=E.parse(p/'landscaped.net.xml');decor=E.parse(p/'scenery.add.xml');r=decor.getroot()
for el in list(r):
 if el.get('type') in ('osm_building','bridge_decoration','satellite_approx_building'):r.remove(el)
roadpoints=[tuple(map(float,q.split(',')))[:2] for lane in n.findall('./edge/lane') for q in lane.get('shape').split()]
def poly(pid,pts,color,z,kind):
 E.SubElement(r,'poly',id=pid,type=kind,shape=shape(pts),fill='true',color=color,layer=str(z))
traci.start(['sumo','-c',str(p/'review.sumocfg'),'--no-step-log','true'])
boxes=[];buildings=[]
for way in s.findall('way'):
 tags={t.get('k'):t.get('v') for t in way.findall('tag')}
 if 'building' not in tags:continue
 refs=[x.get('ref') for x in way.findall('nd')]
 if any(ref not in nodes for ref in refs):continue
 pts=[traci.simulation.convertGeo(*nodes[ref],fromGeo=True) for ref in refs]
 if len(pts)<4:continue
 x0=min(q[0] for q in pts);x1=max(q[0] for q in pts);y0=min(q[1] for q in pts);y1=max(q[1] for q in pts)
 if not (1150<x0<x1<2400 and 450<y0<y1<1900):continue
 if any(x0-6<x<x1+6 and y0-6<y<y1+6 for x,y in roadpoints):continue
 ident=way.get('id');boxes.append((x0-3,y0-3,x1+3,y1+3))
 poly('building_shadow_'+ident,[(x+2,y-2) for x,y in pts],'120,128,124',-7,'osm_building')
 poly('building_roof_'+ident,pts,'177,184,181',-6,'osm_building')
 E.SubElement(r,'poly',id='building_border_'+ident,type='osm_building',shape=shape(pts),fill='false',color='100,111,113',layer='-5.9',lineWidth='.5')
 buildings.append(ident)
traci.close()
# Approximate the eastern low-rise/warehouse cluster in the user-supplied image.
# These are illustrative footprints, explicitly distinct from surveyed OSM ways.
import math
approximate=[]
for i,(x,y,w,h,angle) in enumerate([(1995,1440,22,35,-12),(2040,1400,18,31,-12),(2015,1280,20,47,8),(1985,1170,16,32,8),(2070,1110,25,46,-15),(2020,1020,30,19,-15),(2080,960,22,30,-15)]):
    a=math.radians(angle)
    pts=[(x+u*math.cos(a)-v*math.sin(a),y+u*math.sin(a)+v*math.cos(a)) for u,v in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2),(-w/2,-h/2)]]
    box=(min(q[0] for q in pts)-3,min(q[1] for q in pts)-3,max(q[0] for q in pts)+3,max(q[1] for q in pts)+3)
    if any(box[0]-6<xx<box[2]+6 and box[1]-6<yy<box[3]+6 for xx,yy in roadpoints):continue
    boxes.append(box);approximate.append({'x':x,'y':y,'width':w,'length':h,'basis':'user satellite screenshot; approximate, not surveyed'})
    poly('approx_shadow_'+str(i),[(xx+3,yy-3) for xx,yy in pts],'110,121,116',-7,'satellite_approx_building')
    poly('approx_roof_'+str(i),pts,['177,186,184','142,169,174','173,155,143'][i%3],-6,'satellite_approx_building')
    E.SubElement(r,'poly',id='approx_border_'+str(i),type='satellite_approx_building',shape=shape(pts),fill='false',color='95,110,113',layer='-5.9',lineWidth='.6')
# Remove decorative trees whose crowns would cover a building.
remove=set()
for el in r:
 if el.get('id','').startswith('tree_'):
  pts=[tuple(map(float,q.split(','))) for q in el.get('shape').split()];x=sum(q[0] for q in pts)/len(pts);y=sum(q[1] for q in pts)/len(pts)
  if any(a-7<x<c+7 and b-7<y<d+7 for a,b,c,d in boxes):remove.add(el.get('id').split('_')[-1])
for el in list(r):
 if el.get('type')=='illustrative_greenery' and el.get('id').split('_')[-1] in remove:r.remove(el)
bridgeids={e['edge'] for e in json.loads((p/'elevation-assumptions.json').read_text())}
for edge in n.findall('edge'):
 if edge.get('id') not in bridgeids:continue
 lanes=edge.findall('lane')
 for side,lane in [(1,lanes[0]),(-1,lanes[-1])]:
  pts=[tuple(map(float,q.split(','))) for q in lane.get('shape').split()];w=float(lane.get('width','3.2'))
  inner=shifted(pts,side*(w/2+.1));outer=shifted(pts,side*(w/2+1.1))
  for i in range(len(pts)-1):
   z=min(pts[i][2],pts[i+1][2]);poly(f'bridge_rim_{edge.get("id")}_{side}_{i}',[inner[i],inner[i+1],outer[i+1],outer[i]],'168,179,182',z+.12,'bridge_decoration')
   if side==1:
    far=shifted(pts,side*(w/2+3.8))
    poly(f'bridge_shadow_{edge.get("id")}_{i}',[outer[i],outer[i+1],far[i+1],far[i]],'100,113,107',-.4,'bridge_decoration')
decor.write(p/'scenery.add.xml',encoding='utf-8',xml_declaration=True)
print('OSM buildings:',len(buildings),'bridge edges:',len(bridgeids),'removed overlapping trees:',len(remove))
(p/'building-display-audit.json').write_text(json.dumps({'osm_building_ids':buildings,'approximate_eastern_buildings':approximate,'bridge_edges':sorted(bridgeids),'building_height':'Not inferred; footprint visualization only','bridge_details':'Illustrative deck rim and shadow; not surveyed supports'},indent=2),encoding='utf-8')


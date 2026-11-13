"""Review every traversable junction with actual lane geometry and internal links."""
import json, math, hashlib, xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw
from utils.rebuild_osm_map import DEST

def points(s):return [tuple(map(float,p.split(',')[:2])) for p in s.split()]
def angle(a,b):
 n=math.hypot(*a)*math.hypot(*b)
 return math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(a,b))/n)))) if n>1e-8 else 0

def main():
 root=ET.parse(DEST/'network.net.xml').getroot()
 edges={e.get('id'):e for e in root.findall('edge') if e.get('function')!='internal'}
 lanes={l.get('id'):l for e in root.findall('edge') for l in e.findall('lane')}
 connections=root.findall('connection');rows=[]
 for j in root.findall('junction'):
  ins=[e for e in edges.values() if e.get('to')==j.get('id')];outs=[e for e in edges.values() if e.get('from')==j.get('id')]
  if not ins or not outs:continue
  relevant=[c for c in connections if c.get('from') in {e.get('id') for e in ins}]
  jumps=[]
  for c in relevant:
   a=points(lanes[c.get('from')+'_'+c.get('fromLane')].get('shape'))
   b=points(lanes[c.get('to')+'_'+c.get('toLane')].get('shape'))
   v=points(lanes[c.get('via')].get('shape')) if c.get('via') in lanes else [a[-1],b[0]]
   nonzero=lambda p:[(y[0]-x[0],y[1]-x[1]) for x,y in zip(p,p[1:]) if math.dist(x,y)>.05]
   av,bv,vv=nonzero(a),nonzero(b),nonzero(v)
   if av and bv and vv:
    jumps.append(dict(source=c.get('from')+'_'+c.get('fromLane'),target=c.get('to')+'_'+c.get('toLane'),angle=max(angle(av[-1],vv[0]),angle(vv[-1],bv[0]))))
  rows.append(dict(id=j.get('id'),incoming=[e.get('id') for e in ins],outgoing=[e.get('id') for e in outs],max_link_tangent_jump=max([x['angle'] for x in jumps],default=0),links=jumps))
 output=DEST/'geometry-review';output.mkdir(exist_ok=True)
 for batch in range(0,len(rows),9):
  canvas=Image.new('RGB',(1500,1500),'white');draw=ImageDraw.Draw(canvas)
  for index,row in enumerate(rows[batch:batch+9]):
   j=next(j for j in root.findall('junction') if j.get('id')==row['id']);poly=points(j.get('shape'));cx=sum(p[0] for p in poly)/len(poly);cy=sum(p[1] for p in poly)/len(poly);radius=max(35,max(max(abs(x-cx),abs(y-cy)) for x,y in poly)+20)
   tile=Image.new('RGB',(500,500),'#f7f7f7');td=ImageDraw.Draw(tile)
   def xy(p):return (250+(p[0]-cx)*220/radius,270-(p[1]-cy)*220/radius)
   td.polygon([xy(p) for p in poly],fill='#dddddd',outline='#ff8800')
   for e in root.findall('edge'):
    internal=e.get('function')=='internal'
    for l in e.findall('lane'):
     p=points(l.get('shape'))
     if not any(abs(x-cx)<radius*2 and abs(y-cy)<radius*2 for x,y in p):continue
     td.line([xy(q) for q in p],fill='#3978cc' if internal else '#222222',width=2)
   td.rectangle((0,0,499,499),outline='#aaa');td.rectangle((0,0,499,22),fill='white');td.text((8,5),row['id']+' | jump '+str(round(row['max_link_tangent_jump'],1)),fill='black')
   canvas.paste(tile,((index%3)*500,(index//3)*500))
  canvas.save(output/f'junctions-{batch//9+1}.png')
 endpoint_gaps=[]
 for c in connections:
  source=lanes[c.get('from')+'_'+c.get('fromLane')]
  target=lanes[c.get('via') or c.get('to')+'_'+c.get('toLane')]
  gap=math.dist(points(source.get('shape'))[-1],points(target.get('shape'))[0])
  if gap>.05:endpoint_gaps.append(dict(source=source.get('id'),target=target.get('id'),gap_m=gap))
 external_checks=[]
 for e in edges.values():
  for l in e.findall('lane'):
   p=points(l.get('shape'));v=[(b[0]-a[0],b[1]-a[1]) for a,b in zip(p,p[1:]) if math.dist(a,b)>.1]
   external_checks.append(dict(lane=l.get('id'),max_polyline_angle=max([angle(a,b) for a,b in zip(v,v[1:])],default=0)))
 max_external=max(x['max_polyline_angle'] for x in external_checks)
 max_jump=max(x['max_link_tangent_jump'] for x in rows)
 report=dict(connection_endpoint_gaps_over_5cm=endpoint_gaps,network_sha256=hashlib.sha256((DEST/'network.net.xml').read_bytes()).hexdigest(),junction_count=len(rows),external_lane_count=len(external_checks),max_external_polyline_angle_deg=max_external,max_link_tangent_jump_deg=max_jump,junctions=rows,external_lanes=external_checks,limitations=['Geometric continuity diagnostics, not proof of satellite accuracy or traffic capacity','Short straight-connection rounding can create small nonzero angle measurements'])
 (DEST/'geometry-review.json').write_text(json.dumps(report,indent=2)+'\n')
 assert not endpoint_gaps,endpoint_gaps
 assert max_external<10,('external lane kink',max_external)
 assert max_jump<10,('junction tangent discontinuity',max_jump)
 print(json.dumps(sorted([(r['id'],round(r['max_link_tangent_jump'],2)) for r in rows],key=lambda x:-x[1])[:25]))
if __name__=='__main__':main()

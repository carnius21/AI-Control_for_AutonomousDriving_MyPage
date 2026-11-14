"""Render audited SUMO coordinates as five before/after panels."""
from pathlib import Path
import json,xml.etree.ElementTree as E
from PIL import Image,ImageDraw,ImageFont
from utils.extend_entry_preparation import ROOT,EXTENSIONS,LABELS

def render():
 before=E.parse(ROOT/'maps/toegyewon_north400/network.net.xml');after=E.parse(ROOT/'maps/toegyewon_entryprep/network.net.xml')
 report=json.loads((ROOT/'maps/toegyewon_entryprep/network.net.xml.entry-audit.json').read_text())
 audit={r['entry']:r for r in report['after']};old={r['entry']:r for r in report['before']}
 font=lambda n:ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',n)
 img=Image.new('RGB',(1560,1570),'#eaf0f3');d=ImageDraw.Draw(img)
 d.text((30,18),'퇴계원IC 입구별 첫 분기 준비 거리 · BEFORE / AFTER',font=font(30),fill='#183344')
 d.text((30,65),'북쪽은 +400m → +300m로 조정 / 나머지 짧은 입구는 +100~250m',font=font(22),fill='#456474')
 def pts(s):return [[float(v) for v in token.split(',')[:2]] for token in s.split()]
 for k,eid in enumerate(EXTENSIONS):
  x0=20+(k%2)*770;y0=120+(k//2)*475
  d.rounded_rectangle((x0,y0,x0+750,y0+455),radius=12,fill='white')
  d.text((x0+15,y0+10),LABELS[eid],font=font(23),fill='#183344')
  pre=old[eid]['distance']+(400 if eid=='86198728' else 0);post=audit[eid]['distance']
  subtitle='북쪽 기존 연장을 100m 축소' if eid=='86198728' else f'시작 구간 +{EXTENSIONS[eid]}m 연장'
  d.text((x0+15,y0+42),subtitle,font=font(18),fill='#657c88')
  cloud=[]
  for tree in (before,after):
   for edgeid in audit[eid]['path']:cloud+=pts(tree.find(f"edge[@id='{edgeid}']").get('shape'))
  xmin=min(p[0] for p in cloud)-35;xmax=max(p[0] for p in cloud)+35;ymin=min(p[1] for p in cloud)-35;ymax=max(p[1] for p in cloud)+35
  scale=min(345/(xmax-xmin),300/(ymax-ymin))
  for side,(tree,title) in enumerate([(before,f'BEFORE  {pre:.1f}m'),(after,f'AFTER  {post:.1f}m')]):
   panel=Image.new('RGB',(355,335),'#f3f6f6');pd=ImageDraw.Draw(panel)
   def xy(p):return (177.5+(p[0]-(xmin+xmax)/2)*scale,167.5-(p[1]-(ymin+ymax)/2)*scale)
   for edge in tree.findall('edge'):
    for lane in edge.findall('lane'):
     ps=pts(lane.get('shape'));pd.line([xy(p) for p in ps],fill='#b8c5cd',width=max(1,round(3.2*scale)))
   for edgeid in audit[eid]['path']:
    edge=tree.find(f"edge[@id='{edgeid}']")
    for lane in edge.findall('lane'):
     ps=pts(lane.get('shape'));pd.line([xy(p) for p in ps],fill='#294c68',width=max(2,round(3.2*scale)))
     if edgeid==eid and (side==1 or eid=='86198728'):
      pd.line([xy(p) for p in ps[:2]],fill='#00a6a6' if side else '#cf924f',width=max(2,round(3.2*scale)))
   target=pts(tree.find(f"edge[@id='{audit[eid]['fork_edge']}']").get('shape'))[-1];x,y=xy(target);pd.ellipse((x-4,y-4,x+4,y+4),fill='#ee713e')
   px=x0+15+side*370;py=y0+95;img.paste(panel,(px,py));d.text((px,y0+70),title,font=font(18),fill='#008b8b' if side else '#294c68')
  if eid=='169728849':d.text((x0+15,y0+430),'※ 1차로 입구: 합류 후 실제 차로선택 구간은 67.4m로 동일',font=font(17),fill='#9a5d31')
 x0=790;y0=1070;d.rounded_rectangle((x0,y0,x0+750,y0+455),radius=12,fill='white')
 lines=['09번 입구는 변경 없음','','분기 없이 직진하는 경로이므로 연장 제외.','','청록색: 새로 연장한 구간','남색: 입구부터 첫 분기까지의 경로','주황색 점: 첫 분기 위치 (변경 없음)','','거리: 차로 길이 + 연결부를 포함한 보수적 최솟값','첫 분기까지 거리 ≠ 전 구간에서 차로변경 가능']
 for i,line in enumerate(lines):d.text((x0+22,y0+25+i*36),line,font=font(22 if i==0 else 19),fill='#183344' if i==0 else '#46616f')
 d.text((30,1535),'실제 SUMO 차로 좌표로 작성 · 패널 안 before/after는 같은 축척 · 원본 및 +400m 버전 보존',font=font(18),fill='#456474')
 out=ROOT/'docs/images/toegyewon-entryprep-before-after.png';img.save(out);print(out)
if __name__=='__main__':render()

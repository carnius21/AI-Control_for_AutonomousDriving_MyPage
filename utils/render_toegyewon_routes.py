"""Render the exact 16 network routes as separate panels and a 4x4 atlas."""
import json, math
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets/toegyewon-routes';OUT.mkdir(parents=True,exist_ok=True)
M=json.loads((ROOT/'maps/toegyewon_only/manifest.json').read_text())
NET=ET.parse(ROOT/'maps/toegyewon_only/network.net.xml').getroot()
EDGES={e.get('id'):e for e in NET.findall('edge') if not e.get('function')}
def pts(s):return [tuple(map(float,p.split(',')[:2])) for p in s.split()]
def center(e):return pts(e.get('shape') or e.find('lane').get('shape'))
FONT='C:/Windows/Fonts/malgun.ttf';BOLD='C:/Windows/Fonts/malgunbd.ttf'
def ft(n,b=False):return ImageFont.truetype(BOLD if b else FONT,n)
entries={'169728849':'동쪽 상단 램프','52873356':'남쪽 본선','544295537':'동쪽 상단 본선','556956812#1':'동쪽 금강로','781184662#1':'서쪽 금강로','86198728':'북쪽 본선'}
exits={'1414146971':'북쪽 본선','169728835':'동쪽 남측 도로','169929503#2':'서쪽 금강로','781184662#3':'동쪽 금강로','844484877#1':'남쪽 본선'}
W,H=670,900
scale=min((W-115)/(2050-1320),(H-210)/(1750-600))
def xy(p):return (W/2+(p[0]-1685)*scale,155+(1750-p[1])*scale)
def arrow(d,a,b,color,size=11):
 dx,dy=b[0]-a[0],b[1]-a[1];n=math.hypot(dx,dy)
 if n<.01:return
 ux,uy=dx/n,dy/n
 d.polygon([b,(b[0]-size*ux+size*.5*uy,b[1]-size*uy-size*.5*ux),(b[0]-size*ux-size*.5*uy,b[1]-size*uy+size*.5*ux)],fill=color)
def point_at(ps,length):
 for a,b in zip(ps,ps[1:]):
  n=math.dist(a,b)
  if length<=n:return (a[0]+(b[0]-a[0])*length/n,a[1]+(b[1]-a[1])*length/n)
  length-=n
 return ps[-1]
for i,(rid,path) in enumerate(M['routes'].items(),1):
 im=Image.new('RGB',(W,H),'#ffffff');d=ImageDraw.Draw(im)
 d.rounded_rectangle((1,1,W-2,H-2),radius=18,outline='#cfd8e3',width=2)
 d.rounded_rectangle((22,22,84,68),radius=10,fill='#174c79');d.text((53,43),f'{i:02}',font=ft(28,True),fill='white',anchor='mm')
 d.text((102,24),entries[path[0]]+' →',font=ft(26,True),fill='#172f44')
 d.text((102,62),exits[path[-1]],font=ft(26,True),fill='#172f44')
 # Same scale and orientation on every panel. All actual external road axes.
 for e in EDGES.values():
  ps=[xy(p) for p in center(e)]
  d.line(ps,fill='#ccd4db',width=max(3,round(len(e.findall('lane'))*3.2*scale)),joint='curve')
 # Draw each selected road and the small junction gaps continuously.
 route=[]
 for eid in path:route.extend(xy(p) for p in center(EDGES[eid]))
 d.line(route,fill='#ffffff',width=12,joint='curve')
 d.line(route,fill='#147ec1',width=7,joint='curve')
 length=sum(math.dist(a,b) for a,b in zip(route,route[1:]))
 for pos in range(48,int(length)-20,85):arrow(d,point_at(route,pos-13),point_at(route,pos),'#063e69',13)
 for p,label,color in [(route[0],'출발','#137d59'),(route[-1],'도착','#d34c38')]:
  x,y=p;d.ellipse((x-8,y-8,x+8,y+8),fill=color,outline='white',width=2)
  # Labels on the nearest exterior side, clear of the road drawing.
  lx=x-18 if x<W/2 else x+18;anchor='rm' if x<W/2 else 'lm'
  tw=d.textbbox((0,0),label,font=ft(21,True))[2]
  bx=lx-tw-6 if anchor=='rm' else lx-6
  d.rounded_rectangle((bx,y-17,bx+tw+12,y+18),radius=5,fill='white')
  d.text((lx,y),label,font=ft(21,True),fill=color,anchor=anchor)
 d.text((W-40,125),'N ↑',font=ft(21,True),fill='#758698',anchor='rm')
 d.text((25,H-40),rid,font=ft(18),fill='#7b8996')
 d.text((W-25,H-40),'파란선·화살표 = 주행 경로',font=ft(18),fill='#456078',anchor='ra')
 im.save(OUT/(rid+'.png'))
ATLAS=Image.new('RGB',(W*4+100,H*4+200),'#eef3f7');d=ImageDraw.Draw(ATLAS)
d.text((50,28),'퇴계원IC  ·  16가지 주행 경로',font=ft(46,True),fill='#172f44')
d.text((52,94),'각 그림은 같은 방향·같은 축척  |  초록: 출발  ·  빨강: 도착  |  사노IC를 제외한 테스트 맵',font=ft(25),fill='#4a6276')
for i,rid in enumerate(M['routes']):
 im=Image.open(OUT/(rid+'.png'));ATLAS.paste(im,(20+(i%4)*(W+20),155+(i//4)*(H+10)))
ATLAS.save(OUT/'toegyewon-16-routes.png')
print(OUT/'toegyewon-16-routes.png')

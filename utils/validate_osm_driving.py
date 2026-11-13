"""Small network passage regression, not AV training or traffic performance evaluation."""
import json, os, xml.etree.ElementTree as ET
os.environ['IC_LIBSUMO']='1'
from env.sumo_env import traci
from sumolib import checkBinary
import sumolib
from utils.rebuild_osm_map import DEST

def main():
    net=sumolib.net.readNet(str(DEST/'network.net.xml'))
    cases=[('short_north','169929488#0','1414146971',0),
           ('pocket_right','170059993#1','1414146971',0),
           ('pocket_left','170059993#1','206426298#1',1),
           ('pocket_entry_right','170059993','1414146971',0),
           ('pocket_entry_left','170059993','206426298#1',0),
           ('loop_merge','170059989','206426298#1',0)]
    cases += [(f'mainline_{i}','37927509','206426298#1',i) for i in range(4)]
    cases += [(f'south_ramp_{i}','169929488#1','844484877#1',i) for i in range(2)]
    cases += [('middle_right','781184662#3','169929484',0),
              ('middle_through_1','781184662#3','169929497',1),
              ('middle_through_2','781184662#3','169929497',2),
              ('middle_entering','797789364','169929484',0),
              ('middle_mainline','781184662#2','169929497',0)]
    cases += [(f'north_auxiliary_{i}','844484878#1','1414146971',i) for i in range(5)]
    cases += [('crest_entering_ramp','169728849','169929488#1',0)]
    # Every external lane connection, including all 68 traversable junctions.
    root=ET.parse(DEST/'network.net.xml').getroot()
    for c in root.findall('connection'):
        if c.get('from','').startswith(':') or c.get('to','').startswith(':'):continue
        cases.append(('link_'+c.get('from')+'_'+c.get('fromLane')+'__'+c.get('to')+'_'+c.get('toLane'),c.get('from'),c.get('to'),int(c.get('fromLane'))))
    rows=[]
    for name,start,end,lane in cases:
        path,_=net.getShortestPath(net.getEdge(start),net.getEdge(end),vClass='passenger')
        assert path,name
        route=[e.getID() for e in path]
        traci.start([checkBinary('sumo'),'-c',str(DEST/'review.sumocfg'),'--no-step-log','true','--time-to-teleport','-1'])
        arrived=False;collisions=0;teleports=0
        try:
            traci.route.add('route',route)
            traci.vehicle.add('probe','route',departLane=str(lane),departSpeed='0' if name.startswith('link_') else '5',departPos=str(max(0,net.getEdge(start).getLane(lane).getLength()-25)) if name.startswith('link_') else 'base')
            for t in range(600):
                traci.simulationStep()
                collisions+=traci.simulation.getCollidingVehiclesNumber()
                teleports+=traci.simulation.getStartingTeleportNumber()
                if 'probe' in traci.simulation.getArrivedIDList():arrived=True;break
        finally:traci.close()
        rows.append(dict(case=name,route=route,depart_lane=lane,arrived=arrived,seconds=t+1,collisions=collisions,teleports=teleports))
    report=dict(purpose='SUMO default-driver network passage only; no HV traffic, no AV/RL evaluation',cases=rows)
    (DEST/'ramp-smoke-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    assert all(r['arrived'] and not r['collisions'] and not r['teleports'] for r in rows),[r for r in rows if not r['arrived'] or r['collisions'] or r['teleports']]
    print(f"{len(rows)}/{len(rows)} passed; no collisions or teleports")
if __name__=='__main__':main()

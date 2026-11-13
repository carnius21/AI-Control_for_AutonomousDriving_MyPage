"""Rebuild the review map directly from the user-supplied OSM, no hand-shaped roads."""
import math
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'maps/toegyewon_osm'
ROAD_TYPES={'motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link','unclassified','residential','living_street','service','road'}

def build():
    from env.sumo_env import traci  # installed SUMO discovery only
    from sumolib import checkBinary
    original=ET.parse(DEST/'source.osm').getroot()
    ways={w.get('id'):w for w in original.findall('way') if any(t.get('k')=='highway' and t.get('v') in ROAD_TYPES for t in w.findall('tag'))}
    referenced={n.get('ref') for w in ways.values() for n in w.findall('nd')}
    nodes={n.get('id'):n for n in original.findall('node') if n.get('id') in referenced}
    prepared=ET.Element('osm',version='0.6',generator='project road-only input filter')
    bounds=original.find('bounds');prepared.append(bounds)
    for node in nodes.values():prepared.append(node)
    for way in ways.values():prepared.append(way)
    dropped=[];kept=[]
    for relation in original.findall('relation'):
        tags={t.get('k'):t.get('v') for t in relation.findall('tag')}
        if tags.get('type')!='restriction':continue
        complete=all((m.get('ref') in ways if m.get('type')=='way' else m.get('ref') in nodes if m.get('type')=='node' else False) for m in relation.findall('member'))
        if complete:prepared.append(relation);kept.append(relation.get('id'))
        else:dropped.append(relation.get('id'))
    ET.ElementTree(prepared).write(DEST/'road-input.osm',encoding='utf8',xml_declaration=True)
    bbox=','.join(bounds.get(k) for k in ('minlon','minlat','maxlon','maxlat'))
    args=[checkBinary('netconvert'),'--osm-files','road-input.osm','--output-file','full-import.net.xml','--keep-edges.by-vclass','passenger,bus','--keep-edges.in-geo-boundary',bbox,'--geometry.remove','false','--ramps.guess','false','--osm.layer-elevation','0','--osm.turn-lanes','true','--osm.lane-access','true','--no-turnarounds','true','--junctions.corner-detail','8','--junctions.internal-link-detail','12','--output.original-names','true']
    result=subprocess.run(args,cwd=DEST,capture_output=True,text=True,encoding='utf8',errors='replace')
    (DEST/'conversion-warnings.txt').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    result.check_returncode()
    # Split the returning loop before lane/junction recomputation. Otherwise its nearby
    # endpoints can make netconvert clip away the complete loop at the merge polygon.
    loop_patch=ET.Element('edges');loop=ET.SubElement(loop_patch,'edge',id='170059989')
    ET.SubElement(loop,'split',pos='120',idBefore='170059989',idAfter='170059989#1')
    ET.ElementTree(loop_patch).write(DEST/'loop-split.edg.xml',encoding='utf8',xml_declaration=True)
    subprocess.run([checkBinary('netconvert'),'--sumo-net-file','full-import.net.xml','--edge-files','loop-split.edg.xml','--output-file','full-import.net.xml','--no-turnarounds','true'],cwd=DEST,capture_output=True,check=True)
    scope=json.loads((DEST/'scope.json').read_text(encoding='utf8'))
    full=ET.parse(DEST/'full-import.net.xml').getroot()
    existing={e.get('id') for e in full.findall('edge')}
    missing=set(scope['edges'])-existing
    if missing:raise ValueError(f'Scope edges missing from source import: {missing}')
    overrides=json.loads((DEST/'lane-overrides.json').read_text(encoding='utf8'))
    markings=json.loads((DEST/'markings.json').read_text(encoding='utf8'))
    corrections=ET.Element('edges')
    for eid,item in overrides.items():
        if eid not in scope['edges']:raise ValueError(f'Override outside selected scope: {eid}')
        ET.SubElement(corrections,'edge',id=eid,numLanes=str(item['num_lanes']))
    full_edges={e.get('id'):e for e in full.findall('edge')}
    # Round survey-polyline corners locally, never moving endpoints or the road corridor.
    # Round every curved road, bounded to <= 4 m from the original corridor.
    rounded={}
    for eid in scope['edges']:
        if not full_edges[eid].get('shape'):continue
        pts=[tuple(map(float,p.split(','))) for p in full_edges[eid].get('shape').split()]
        out=[pts[0]]
        for a,b,c in zip(pts,pts[1:],pts[2:]):
            ab=math.dist(a,b);bc=math.dist(b,c)
            if min(ab,bc)<.001:continue
            cosine=sum((b[k]-a[k])*(c[k]-b[k]) for k in range(2))/(ab*bc)
            sine_half=math.sqrt(max(0.,(1-min(1.,max(-1.,cosine)))/2))
            d=min(20.,ab*.45,bc*.45,8./max(sine_half,.001))
            u=tuple(b[k]+(a[k]-b[k])*d/ab for k in range(2))
            v=tuple(b[k]+(c[k]-b[k])*d/bc for k in range(2))
            out.append(u)
            for step in range(1,13):
                t=step/12
                out.append(tuple((1-t)**2*u[k]+2*t*(1-t)*b[k]+t*t*v[k] for k in range(2)))
        out.append(pts[-1]);rounded[eid]=out
        edge=next((e for e in corrections if e.get('id')==eid),None)
        if edge is None:edge=ET.SubElement(corrections,'edge',id=eid)
        edge.set('shape',' '.join(f'{x:.2f},{y:.2f}' for x,y in out))

    adjustments=json.loads((DEST/'layout-adjustments.json').read_text(encoding='utf8'))
    for eid,shape in adjustments.get('junction_smoothing',{}).items():
        edge=next((e for e in corrections if e.get('id')==eid),None)
        if edge is None:edge=ET.SubElement(corrections,'edge',id=eid)
        edge.set('shape',shape)
    north=adjustments['north_merge'];edge=next(e for e in corrections if e.get('id')==north['edge'])
    edge.set('to',north['to']);edge.set('shape',north['shape'])
    for eid,shape in adjustments.get('north_boundary_edges',{}).items():
        edge=next((e for e in corrections if e.get('id')==eid),None)
        if edge is None:edge=ET.SubElement(corrections,'edge',id=eid)
        edge.set('shape',shape)
    # Added auxiliary lane belongs on the driving-right side; retain mainline alignment.
    # Center-spreading five lanes on the old four-lane axis shifts every through lane.
    from sumolib.geomhelper import move2side
    junctions={j.get('id'):j for j in full.findall('junction')}
    for eid in ('844484878#1','86198722','86198708'):
        auxiliary=next(e for e in corrections if e.get('id')==eid)
        source_edge=full_edges[eid]
        if auxiliary.get('shape'):
            points=[tuple(map(float,p.split(','))) for p in auxiliary.get('shape').split()]
        else:
            points=[(float(junctions[source_edge.get(side)].get('x')),float(junctions[source_edge.get(side)].get('y'))) for side in ('from','to')]
        points=move2side(points,1.6)
        auxiliary.set('shape',' '.join(f'{x:.2f},{y:.2f}' for x,y in points))
    north_nodes=ET.Element('nodes')
    for nid,(x,y) in {**adjustments.get('north_boundary_nodes',{}),**adjustments.get('junction_node_adjustments',{})}.items():
        ET.SubElement(north_nodes,'node',id=nid,x=str(x),y=str(y))
    ET.ElementTree(north_nodes).write(DEST/'north-boundary.nod.xml',encoding='utf8',xml_declaration=True)
    pocket_edge=next((e for e in corrections if e.get('id')==adjustments['pocket']['approach']),None)
    if pocket_edge is None:pocket_edge=ET.SubElement(corrections,'edge',id=adjustments['pocket']['approach'])
    pocket_edge.set('numLanes','2')
    for eid in markings['solid']:

        if eid not in scope['edges']:raise ValueError(f'Marking outside scope: {eid}')
        edge=next((e for e in corrections if e.get('id')==eid),None)
        if edge is None:edge=ET.SubElement(corrections,'edge',id=eid)
        count=overrides.get(eid,{}).get('num_lanes',len(full_edges[eid].findall('lane')))
        for i in range(count):
            attrs={'index':str(i)}
            if i<count-1:attrs['changeLeft']=markings['solid_allowed_classes']
            if i>0:attrs['changeRight']=markings['solid_allowed_classes']
            ET.SubElement(edge,'lane',**attrs)
    ET.ElementTree(corrections).write(DEST/'lane-overrides.edg.xml',encoding='utf8',xml_declaration=True)
    # A net.xml import keeps obsolete lane links unless explicitly reset (SUMO PlainXML).
    affected=set(overrides)|set(markings['solid'])|{adjustments['pocket']['approach'],'86198708'}
    incoming={c.get('from') for c in full.findall('connection') if c.get('to') in affected}
    reset_edges=(affected|incoming)&set(scope['edges'])
    links=ET.Element('connections')
    explicit=json.loads((DEST/'connection-overrides.json').read_text(encoding='utf8'))['connections']
    explicit_from={c['from'] for c in explicit}
    for eid in sorted(reset_edges-explicit_from):ET.SubElement(links,'connection',{'from':eid,'reset':'true'})
    for before,after in sorted({(c['from'],c['to']) for c in explicit}):ET.SubElement(links,'delete',{'from':before,'to':after})
    for c in explicit:ET.SubElement(links,'connection',{k:str(v) for k,v in c.items()})
    ET.ElementTree(links).write(DEST/'connection-resets.con.xml',encoding='utf8',xml_declaration=True)
    crop_args=[checkBinary('netconvert'),'--sumo-net-file','full-import.net.xml','--edge-files','lane-overrides.edg.xml','--connection-files','connection-resets.con.xml','--node-files','north-boundary.nod.xml','--keep-edges.explicit',','.join(scope['edges']),'--output-file','network.net.xml','--no-turnarounds','true','--geometry.remove','false']
    crop=subprocess.run(crop_args,cwd=DEST,capture_output=True,text=True,encoding='utf8',errors='replace')
    with (DEST/'conversion-warnings.txt').open('a',encoding='utf8') as log:log.write('\nScope crop:\n'+crop.stdout+'\n'+crop.stderr)
    crop.check_returncode()
    # Keep the auxiliary lane through the observed downstream taper, not just to the OSM merge node.
    shape=[tuple(map(float,p.split(','))) for p in full_edges['844484877'].get('shape').split()]
    split_distance=sum(math.dist(a,b) for a,b in zip(shape[:3],shape[1:4]))
    patch=ET.Element('edges');edge=ET.SubElement(patch,'edge',id='844484877')
    ET.SubElement(edge,'split',pos=f'{split_distance:.2f}',lanes='1 2 3 4',idBefore='844484877',idAfter='844484877#1')
    north_drop=ET.SubElement(patch,'edge',id='86198708')
    ET.SubElement(north_drop,'split',pos=str(-adjustments['north_auxiliary_drop']['remaining_m_before_merge']),lanes='1 2 3 4',idBefore='86198708',idAfter='86198708#1')
    pocket=ET.SubElement(patch,'edge',id=adjustments['pocket']['approach'])
    ET.SubElement(pocket,'split',pos='0',lanes='1')
    ET.SubElement(pocket,'split',pos=str(-adjustments['pocket']['last_m']),lanes='0 1',idBefore='170059993',idAfter='170059993#1')
    ET.ElementTree(patch).write(DEST/'auxiliary-taper.edg.xml',encoding='utf8',xml_declaration=True)
    shape2=[tuple(map(float,p.split(','))) for p in full_edges['206426298'].get('shape').split()]
    loop_split=sum(math.dist(a,b) for a,b in zip(shape2[:3],shape2[1:4]))
    loop=ET.SubElement(patch,'edge',id='206426298')
    ET.SubElement(loop,'split',pos=f'{loop_split:.2f}',lanes='1 2 3 4',idBefore='206426298',idAfter='206426298#1')
    ET.ElementTree(patch).write(DEST/'auxiliary-taper.edg.xml',encoding='utf8',xml_declaration=True)
    # Lane reduction at the pocket entrance invalidates the old target lane index.
    split_links=ET.Element('connections')
    ET.SubElement(split_links,'connection',{'from':'781184662#1','reset':'true'})
    ET.ElementTree(split_links).write(DEST/'split-resets.con.xml',encoding='utf8',xml_declaration=True)
    tapered=subprocess.run([checkBinary('netconvert'),'--sumo-net-file','network.net.xml','--edge-files','auxiliary-taper.edg.xml','--connection-files','split-resets.con.xml','--output-file','network.net.xml','--no-turnarounds','true'],cwd=DEST,capture_output=True,text=True,encoding='utf8',errors='replace')
    with (DEST/'conversion-warnings.txt').open('a',encoding='utf8') as log:log.write('\nAuxiliary taper:\n'+tapered.stdout+'\n'+tapered.stderr)
    tapered.check_returncode()
    final_tree=ET.parse(DEST/'network.net.xml')
    final_tree.write(DEST/'network.net.xml',encoding='utf8',xml_declaration=True)
    net=final_tree.getroot();external=[e for e in net.findall('edge') if e.get('function')!='internal']
    audit=[]
    for e in external:
        way_id=e.get('id').lstrip('-').split('#')[0];way=ways.get(way_id)
        tags={t.get('k'):t.get('v') for t in way.findall('tag')} if way is not None else {}
        audit.append(dict(edge=e.get('id'),osm_way=way_id,lanes=len(e.findall('lane')),osm_lanes=tags.get('lanes'),osm_directional_lanes={k:v for k,v in tags.items() if k.startswith('lanes:')},oneway=tags.get('oneway'),highway=tags.get('highway'),maxspeed=tags.get('maxspeed'),layer=tags.get('layer'),bridge=tags.get('bridge'),turn_lanes={k:v for k,v in tags.items() if k.startswith('turn:lanes')},lane_override=({'num_lanes':4,'basis':'north auxiliary drop'} if e.get('id')=='86198708#1' else overrides.get(e.get('id'))),geometry_rounding=(e.get('id') in rounded or e.get('id') in {'170059993#1','206426298#1','844484877#1'}) and e.get('id')!=north['edge'] and e.get('id') not in adjustments.get('north_boundary_edges',{}),layout_adjustment='user_requested_north_shortening' if e.get('id')==north['edge'] else 'advance_fork_pocket' if e.get('id') in ('170059993','170059993#1','544293888#0') else None,marking_status='solid_verified' if e.get('id') in markings['solid'] else 'dashed_verified' if e.get('id') in markings['dashed'] else 'mixed_unresolved' if e.get('id') in markings['unresolved'] else 'not_applicable' if len(e.findall('lane'))==1 else 'unverified',lane_source='Project override ('+overrides[e.get('id')].get('confidence','visible')+')' if e.get('id') in overrides else 'OSM tag (directional split may apply)' if 'lanes' in tags or any(k.startswith('lanes:') for k in tags) else 'SUMO road-type default, unverified'))
    report=dict(source_sha256=hashlib.sha256((DEST/'source.osm').read_bytes()).hexdigest(),source_bounds=bounds.attrib,scope=scope,crop_command=crop_args[1:],command=args[1:],sumo_version=subprocess.check_output([checkBinary('netconvert'),'--version'],text=True).splitlines()[0],external_edges=len(external),lanes=sum(len(e.findall('lane')) for e in external),restriction_relations_kept=kept,incomplete_restrictions_omitted=dropped,edges=audit)
    (DEST/'import-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    # Native lane rendering avoids the old crossing rectangles and hand-drawn stripes.
    view=ET.Element('viewsettings');scheme=ET.SubElement(view,'scheme',name='OSM source geometry - review')
    ET.SubElement(scheme,'background',backgroundColor='235,239,233')
    ET.SubElement(scheme,'edges',laneShowBorders='true',showDirection='false',showLinkDecals='true',widthExaggeration='1')
    ET.SubElement(view,'delay',value='100')
    anchors=[j for j in net.findall('junction') if j.get('id') in ('498837378','1000493460','436249310')]
    x=sum(float(j.get('x')) for j in anchors)/len(anchors)
    y=sum(float(j.get('y')) for j in anchors)/len(anchors)
    ET.SubElement(view,'viewport',x=str(x),y=str(y),zoom='150')
    ET.indent(view);ET.ElementTree(view).write(DEST/'view.xml',encoding='utf8',xml_declaration=True)
    cfg=ET.Element('configuration');inp=ET.SubElement(cfg,'input');ET.SubElement(inp,'net-file',value='network.net.xml')
    gui=ET.SubElement(cfg,'gui_only');ET.SubElement(gui,'gui-settings-file',value='view.xml')
    ET.indent(cfg);ET.ElementTree(cfg).write(DEST/'review.sumocfg',encoding='utf8',xml_declaration=True)
    print(json.dumps({k:report[k] for k in ('external_edges','lanes','source_sha256')},indent=2))
    return DEST/'review.sumocfg'
if __name__=='__main__':build()

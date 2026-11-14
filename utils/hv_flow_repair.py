"""Geometry-preserving, native SUMO HV-only repair trials (no AV control)."""
import argparse
import concurrent.futures
import copy
import functools
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from utils import hv_flow_audit as audit

ROOT = audit.ROOT
SOURCE_NETWORK = ROOT/'maps/toegyewon_only/network.net.xml'
SOURCE_ROUTES = ROOT/'scenarios/hv_stable/source.rou.xml'
JUNCTIONS = ('1808903166', '1000493465', '1810880137')


def connection_key(c):
    return tuple(c.get(k) for k in ('from', 'to', 'fromLane', 'toLane', 'via'))


def validate_geometry(source, target, speed_edges=()):
    before, after = ET.parse(source), ET.parse(target)
    a = {e.get('id'): e for e in before.findall('edge')}
    b = {e.get('id'): e for e in after.findall('edge')}
    assert a.keys() == b.keys(), 'Edge set changed'
    changed_speeds = []
    for eid in a:
        assert a[eid].attrib == b[eid].attrib, ('edge', eid)
        aa, bb = a[eid].findall('lane'), b[eid].findall('lane')
        assert len(aa) == len(bb), ('lane count', eid)
        for left, right in zip(aa, bb):
            la, lb = dict(left.attrib), dict(right.attrib)
            if eid in speed_edges:
                if la.get('speed') != lb.get('speed'):
                    changed_speeds.append(left.get('id'))
                la.pop('speed', None); lb.pop('speed', None)
            assert la == lb, ('lane geometry/permission', left.get('id'))
    assert {j.get('id'):j.get('shape') for j in before.findall('junction')} == {
        j.get('id'):j.get('shape') for j in after.findall('junction')}, 'Junction shape changed'
    assert {connection_key(c) for c in before.findall('connection')} == {
        connection_key(c) for c in after.findall('connection')}, 'Connectivity changed'
    return dict(all_lane_geometry_and_permissions_unchanged=True, connections_unchanged=True,
                junction_shapes_unchanged=True, speed_changed_lanes=changed_speeds,
                weave_length=after.find("edge[@id='170059994']/lane").get('length'))


def preserve_geometry_zipper(source, target, directory):
    """Take ONLY validated right-of-way tables from netconvert, never its geometry."""
    original = ET.parse(source)
    nodes = ET.Element('nodes')
    for jid in JUNCTIONS:
        ET.SubElement(nodes, 'node', id=jid, type='zipper')
    ET.ElementTree(nodes).write(directory/'zipper.nod.xml', encoding='utf8')
    command = [str(audit.SUMO/'bin/netconvert.exe'), '--sumo-net-file', str(source),
               '--node-files', str(directory/'zipper.nod.xml'), '--output-file', str(directory/'generated.net.xml')]
    with (directory/'netconvert.log').open('w', encoding='utf8') as log:
        subprocess.run(command, check=True, stdout=log, stderr=log)
    generated = ET.parse(directory/'generated.net.xml')
    before_lanes = {e.get('id'): dict(e.attrib) for e in original.findall('.//lane')}
    before_junctions = {j.get('id'): j.get('shape') for j in original.findall('junction')}
    before_connections = {connection_key(c) for c in original.findall('connection')}
    regenerated = {connection_key(c): c for c in generated.findall('connection')}
    for jid in JUNCTIONS:
        old = original.find(f"junction[@id='{jid}']")
        new = generated.find(f"junction[@id='{jid}']")
        # Request bits are indexed by incoming/internal lane order. Never transplant
        # a table across different indexing or connectivity.
        for attr in ('incLanes', 'intLanes'):
            assert old.get(attr) == new.get(attr), (jid, attr)
        assert [x.get('index') for x in old.findall('request')] == [x.get('index') for x in new.findall('request')]
        old.set('type', 'zipper')
        for req in list(old.findall('request')):
            old.remove(req)
        for req in new.findall('request'):
            old.append(copy.deepcopy(req))
        incoming = {e.get('id') for e in original.findall('edge') if e.get('to') == jid}
        for c in original.findall('connection'):
            if c.get('from') in incoming:
                c.set('state', regenerated[connection_key(c)].get('state'))
    assert before_lanes == {e.get('id'): dict(e.attrib) for e in original.findall('.//lane')}
    assert before_junctions == {j.get('id'): j.get('shape') for j in original.findall('junction')}
    assert before_connections == {connection_key(c) for c in original.findall('connection')}
    original.write(target, encoding='utf8', xml_declaration=True)
    audit.save(directory/'geometry-check.json', dict(all_lane_attributes_unchanged=True,
        all_junction_shapes_unchanged=True, connections_unchanged=True,
        weave_length=original.find("edge[@id='170059994']/lane").get('length')))


def prepare(out, mode, duration, demand_scale=1.0):
    directory = out/'inputs'/mode
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_NETWORK, directory/'network.net.xml')
    shutil.copy2(SOURCE_ROUTES, directory/'highway.rou.xml')
    (directory/'run.sumocfg').write_text(
        '<configuration><input><net-file value="network.net.xml"/>'
        '<route-files value="highway.rou.xml"/></input><processing>'
        '<time-to-teleport value="-1"/><collision.check-junctions value="true"/>'
        '<collision.action value="remove"/></processing><time><step-length value="0.2"/>'
        '</time></configuration>', encoding='utf8')
    if mode != 'original':
        preserve_geometry_zipper(SOURCE_NETWORK, directory/'network.net.xml', directory)
    tree = ET.parse(directory/'highway.rou.xml')
    for flow in tree.findall('flow'):
        flow.set('end', str(duration))
        if mode in ('balanced', 'cooperative', 'slow', 'capacity', 'drivers'):
            rates = {'route_13': 200, 'route_14': 200, 'route_15': 200, 'route_16': 2400}
            if flow.get('route') in rates:
                flow.set('vehsPerHour', str(rates[flow.get('route')]))
        if mode in ('capacity', 'drivers'):
            rates = {'route_03':450, 'route_04':450, 'route_05':450, 'route_06':1050}
            if flow.get('route') in rates:
                flow.set('vehsPerHour', str(rates[flow.get('route')]))
        flow.set('vehsPerHour', str(float(flow.get('vehsPerHour')) * demand_scale))
    if mode == 'drivers':
        for vt in tree.findall('vType'):
            if 'violator' in vt.get('id'):
                vt.set('lcCooperative', '0')
                vt.set('lcCooperativeSpeed', '0')
    if mode == 'cooperative':
        for vt in tree.findall('vType'):
            if vt.get('id') != 'ego_type' and 'violator' not in vt.get('id'):
                vt.set('lcCooperativeHelpTime', '5')
    if mode in ('slow', 'slow_original', 'capacity', 'drivers'):
        network = ET.parse(directory/'network.net.xml')
        for eid in ('170059991', '170059995', '170059994'):
            for lane in network.find(f"edge[@id='{eid}']").findall('lane'):
                lane.set('speed', '11.11')
        network.write(directory/'network.net.xml', encoding='utf8', xml_declaration=True)
    tree.write(directory/'highway.rou.xml', encoding='utf8', xml_declaration=True)
    audit.save(directory/'geometry-check.json', validate_geometry(SOURCE_NETWORK,
        directory/'network.net.xml', ('170059991','170059995','170059994') if mode in ('slow','slow_original','capacity','drivers') else ()))
    audit.save(directory/'manifest.json', dict(mode=mode, duration=duration,
        source_network=str(SOURCE_NETWORK),source_routes=str(SOURCE_ROUTES),
        total_vph=sum(float(f.get('vehsPerHour')) for f in tree.findall('flow')),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        code_hashes={f:audit.sha(ROOT/'utils'/f) for f in ('hv_flow_repair.py','hv_flow_audit.py')},
        files={f:audit.sha(directory/f) for f in ('network.net.xml','highway.rou.xml','run.sumocfg')}))


def init_worker(out):
    audit.OUT = Path(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--modes', nargs='+', default=['original','zipper','balanced','cooperative'],
                   choices=['original','zipper','balanced','cooperative','slow','slow_original','capacity','drivers'])
    p.add_argument('--seeds', nargs='+', type=int, default=[1001,1002,1003])
    p.add_argument('--duration', type=int, default=900)
    p.add_argument('--horizon', type=int, default=3600)
    p.add_argument('--demand-scale', type=float, default=1.0)
    p.add_argument('--output', default='results/hv_flow_repair_20261113/short')
    p.add_argument('--export', help='Build one scenario only, into a separate repository directory')
    args = p.parse_args()
    if args.demand_scale <= 0 or args.horizon <= args.duration:
        p.error('Demand scale must be positive and horizon must exceed inflow duration')
    out = ROOT/args.output
    out.mkdir(parents=True, exist_ok=True)
    lock = out/'active.lock'
    fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode()); os.close(fd)
    try:
        for mode in args.modes:
            prepare(out, mode, args.duration, args.demand_scale)
        if args.export:
            if len(args.modes) != 1:
                raise ValueError('Export requires exactly one mode')
            destination = ROOT/args.export
            destination.mkdir(parents=True, exist_ok=True)
            for name in ('network.net.xml','highway.rou.xml','run.sumocfg','geometry-check.json','manifest.json'):
                shutil.copy2(out/'inputs'/args.modes[0]/name, destination/name)
            audit.save(out/'status.json', dict(stage='exported', path=str(destination)))
            return
        audit.save(out/'status.json', dict(stage='running',pid=os.getpid()))
        runner = functools.partial(audit.run, horizon=args.horizon, junction_checks=True)
        with concurrent.futures.ProcessPoolExecutor(max_workers=6, initializer=init_worker, initargs=(str(out),)) as pool:
            for result in pool.map(runner, [(m,s) for m in args.modes for s in args.seeds]):
                print(result, flush=True)
        audit.save(out/'status.json', dict(stage='complete'))
    except Exception as exc:
        audit.save(out/'status.json', dict(stage='error', error=repr(exc)))
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    main()

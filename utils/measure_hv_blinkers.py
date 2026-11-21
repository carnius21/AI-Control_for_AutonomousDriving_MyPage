"""Read-only signal timing audit: default HV traffic, no AV or action overrides."""
import collections
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'results/neighbor_fix_20261114/inputs/reference'
OUT = ROOT / 'results/hv_blinkers_20261116'
SUMO = Path(os.environ.get('SUMO_HOME', 'C:/Program Files (x86)/Eclipse/Sumo'))
sys.path.insert(0, str(SUMO / 'tools'))
import traci
import traci.constants as tc


def run(seed):
    folder = OUT / str(seed)
    folder.mkdir(parents=True, exist_ok=True)
    traci.start([str(SUMO/'bin/sumo.exe'), '-c', str(SOURCE/'run.sumocfg'),
                 '--seed', str(seed), '--step-length', '0.2', '--no-step-log', 'true',
                 '--lanechange-output', str(folder/'lanechanges.xml'),
                 '--error-log', str(folder/'sumo.log')])
    previous = {}; types = {}; starts = {}; censored = {}; events = []
    seen = collections.Counter(); onsets = collections.Counter()
    arrived = collisions = teleports = 0
    version = traci.getVersion()
    try:
        for step in range(9000):  # 30 minutes per seed, includes warm-up
            traci.simulationStep()
            now = round((step+1)*.2, 6)
            for vid in traci.simulation.getDepartedIDList():
                types[vid] = traci.vehicle.getTypeID(vid)
                seen[types[vid]] += 1
                traci.vehicle.subscribe(vid, [tc.VAR_ROAD_ID, tc.VAR_LANE_INDEX, tc.VAR_SIGNALS])
            arrived += traci.simulation.getArrivedNumber()
            collisions += traci.simulation.getCollidingVehiclesNumber()
            teleports += traci.simulation.getStartingTeleportNumber()
            states = traci.vehicle.getAllSubscriptionResults()
            for vid, state in states.items():
                edge, lane, signal = (state[k] for k in (tc.VAR_ROAD_ID, tc.VAR_LANE_INDEX, tc.VAR_SIGNALS))
                old = previous.get(vid)
                # Lane-index changes at road boundaries are NOT lane changes.
                if old and edge == old[0] and not edge.startswith(':') and lane != old[1]:
                    bit = 2 if lane > old[1] else 1
                    prior = bool(old[2] & bit)
                    age = round(now-starts[vid,bit],6) if prior else 0.
                    events.append(dict(seed=seed,vehicle=vid,type=types[vid],time=now,
                        edge=edge,from_lane=old[1],to_lane=lane,direction='left' if bit==2 else 'right',
                        prior_signal=prior,lead_seconds=age,
                        onset_censored=bool(censored.get((vid,bit),False)) if prior else False,
                        both_prior=bool(old[2]&1 and old[2]&2),signal_before=old[2],signal_after=signal))
                for bit in (1,2):
                    if signal & bit:
                        if not old or not old[2] & bit:
                            starts[vid,bit] = now
                            censored[vid,bit] = old is None
                            if old: onsets[types[vid]] += 1
                    else:
                        starts.pop((vid,bit),None);censored.pop((vid,bit),None)
                previous[vid]=(edge,lane,signal)
            for vid in set(previous)-set(states):
                previous.pop(vid,None)
                for bit in (1,2):starts.pop((vid,bit),None);censored.pop((vid,bit),None)
            if (step+1)%1500==0: print(seed,now,'seconds',len(events),'changes',flush=True)
    finally:
        traci.close()
    xml_events = list(ET.parse(folder/'lanechanges.xml').getroot())
    # Match recorded physical lane changes to SUMO's independent output, allowing timestep convention.
    matched = 0
    for e in events:
        candidates=[x for x in xml_events if x.tag=='change' and x.get('id')==e['vehicle']
                    and x.get('from')==f"{e['edge']}_{e['from_lane']}"
                    and x.get('to')==f"{e['edge']}_{e['to_lane']}"
                    and abs(float(x.get('time'))-e['time'])<.201]
        if candidates:
            matched+=1;e['reason']=candidates[0].get('reason')
    result=dict(seed=seed,seconds=1800,version=version,seen=dict(seen),arrived=arrived,
        collision_vehicle_events=collisions,teleports=teleports,signal_onsets=dict(onsets),
        matched_xml=matched,xml_change_count=sum(x.tag=='change' for x in xml_events),events=events)
    (folder/'measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result


def summarize(results):
    groups=collections.defaultdict(list)
    for r in results:
        assert r['matched_xml']==len(r['events']), 'Signal samples did not match lane-change output'
        for e in r['events']:groups[e['type']].append(e)
    table=[]
    for kind,es in sorted(groups.items()):
        leads=[e['lead_seconds'] for e in es if e['prior_signal'] and not e['onset_censored'] and not e['both_prior']]
        table.append(dict(type=kind,changes=len(es),prior_signal=sum(e['prior_signal'] for e in es),
            prior_ge1s=sum(e['prior_signal'] and e['lead_seconds']>=1 for e in es),
            censored=sum(e['onset_censored'] for e in es),both_prior=sum(e['both_prior'] for e in es),
            measured_onsets=len(leads),median=statistics.median(leads) if leads else None,
            min=min(leads) if leads else None,max=max(leads) if leads else None))
    report=dict(source=str(SOURCE),seconds_per_seed=1800,seeds=[r['seed'] for r in results],
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*') if p.suffix in ('.xml','.sumocfg')},
        types=[x.attrib for x in ET.parse(SOURCE/'highway.rou.xml').findall('vType')],table=table,
        caveats=['Observational comparison, not isolated car-follow model causality.',
                 '0.2s sampling: zero means no matching signal at previous sample, not proof of never signaling.',
                 'Same-edge lane changes only; road-boundary index changes excluded.',
                 'A matching blinker may also be signaling an upcoming turn; not necessarily a dedicated lane-change announcement.',
                 'Lead time is current uninterrupted signal episode, not a fixed driver timer.'])
    (OUT/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(table,ensure_ascii=False,indent=2))


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
        summarize(list(pool.map(run,[59101,59102,59103])))

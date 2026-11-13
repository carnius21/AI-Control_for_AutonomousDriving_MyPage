"""Frozen-policy no-traffic preflight; preserves the original network and policies."""
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from utils.ic_campaign import OUT, ROOT, PPO, torch, save, digest, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD, TRAFFIC
from env.ic_experiment import ICExperimentEnv
from env.sumo_env import traci
from utils.ic_timeout_trace import TimeoutTrace
DEST=ROOT/'results/ic_no_traffic_v1'
ROUTES=('south_through','south_to_east','north_to_west')
def main():
    torch.set_num_threads(1)
    mapdir=DEST/'map';mapdir.mkdir(parents=True,exist_ok=True)
    for source in (OUT/'maps/base').iterdir():
        if source.is_file() and not (mapdir/source.name).exists(): shutil.copy2(source,mapdir/source.name)
    routefile=mapdir/'highway.rou.xml';tree=ET.parse(routefile)
    for node in list(tree.getroot()):
        if node.tag in ('flow','vehicle','trip'):tree.getroot().remove(node)
    tree.write(routefile,encoding='utf-8',xml_declaration=True)
    assert digest(mapdir/'highway.net.xml')==digest(OUT/'maps/base/highway.net.xml')
    for seed in (11,22,33):
        modeldir=OUT/'runs'/f'R0-{seed}-200000';meta=json.loads((modeldir/'complete.json').read_text())
        for route in ROUTES:
            key=f'R0-{seed}-{route}';target=DEST/'cases'/(key+'.json')
            if target.exists():continue
            save(DEST/'status.json',dict(stage='running_A0',case=key))
            env=ICExperimentEnv(str(mapdir/'highway.sumocfg'),ROAD,dict(EGO,depart_lane='best',depart_speed='max'),SIMULATION,OBSERVATION,ACTION,REWARD,dict(TRAFFIC,demo_vehicle=False,vehs_per_hour=0),(),11)
            try:
                agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp']); agent.load(str(modeldir/'policy-200000.pt'))
                obs,_=env.reset(seed=1001,options={'route':route});trace=TimeoutTrace();count=0
                td=DEST/'traces';td.mkdir(exist_ok=True)
                with (td/(key+'.jsonl')).open('w',encoding='utf8') as stream:
                    while True:
                        assert set(traci.vehicle.getIDList()) <= {env.ego_id},'Background vehicle found'
                        action=agent.predict(obs,deterministic=True)
                        if env.step_count%5==0:
                            trace.sample(env)
                            stream.write(json.dumps(dict(t=env.step_count*env.step_length,context=env.context(),observation=obs.tolist(),action=action.tolist()),ensure_ascii=False)+'\n')
                        obs,_,done,cut,info=env.step(action);count+=1
                        if done or cut:break
                save(target,dict(run=key,route=route,training_seed=seed,simulation_seed=1001,arrival=bool(info['arrived']),collision=bool(info['collided']),timeout=bool(cut and not done),wrong_exit=info['ic_event']['wrong_exit'],seconds=env.step_count*env.step_length,steps=count,diagnostic=trace.result(),policy_sha256=digest(modeldir/'policy-200000.pt'),network_sha256=digest(mapdir/'highway.net.xml'),git=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
            finally:env.close()
    save(DEST/'status.json',dict(stage='A0_complete',cases=9,next='Review failures and implement B/C before A1 or retraining'))
if __name__=='__main__':main()

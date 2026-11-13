"""Resume timeout-only replay of completed final checkpoints; run again for new runs."""
import json
from utils.ic_campaign import OUT, environment, PPO, torch, save, digest
from utils.ic_timeout_trace import TimeoutTrace

def main():
    torch.set_num_threads(1)
    output=OUT/'timeout-diagnostics'
    for manifest in sorted((OUT/'runs').glob('*/complete.json')):
        meta=json.loads(manifest.read_text(encoding='utf8'))
        if meta['budget']!=200000: continue
        folder=manifest.parent
        evaluation=folder/'eval-200000.json'
        rows=json.loads(evaluation.read_text(encoding='utf8'))['rows']
        target=output/(folder.name+'.json')
        recorded=json.loads(target.read_text(encoding='utf8')) if target.exists() else dict(run=folder.name, policy_sha256=digest(folder/'policy-200000.pt'), evaluation_sha256=digest(evaluation), cases=[])
        if recorded['policy_sha256']!=digest(folder/'policy-200000.pt') or recorded['evaluation_sha256']!=digest(evaluation): raise RuntimeError('Replay input changed')
        known={(r['route'],r['seed'],r['load']) for r in recorded['cases']}
        for row in rows:
            key=(row['route'],row['seed'],row['load'])
            if not row['timeout'] or key in known: continue
            save(output/'status.json',dict(stage='replaying',run=folder.name,route=row['route'],seed=row['seed']))
            env=environment(meta['variants'],11,row['load'])
            try:
                agent=PPO(obs_dim=env.obs_dim,act_dim=env.act_dim,**meta['hp'])
                agent.load(str(folder/'policy-200000.pt'))
                obs,_=env.reset(seed=row['seed'],options={'route':row['route']})
                trace=TimeoutTrace()
                while True:
                    if env.step_count % 5 == 0: trace.sample(env)
                    obs,_,done,cut,info=env.step(agent.predict(obs,deterministic=True))
                    if done or cut: break
                matched=bool(cut and not done) and abs(env.step_count*env.step_length-row['seconds'])<.001
                diagnostic=trace.result()
                if not matched: diagnostic['category']='replay_mismatch'
                recorded['cases'].append(dict(route=row['route'],seed=row['seed'],load=row['load'],matched=matched,**diagnostic))
                save(target,recorded)
            finally: env.close()
    save(output/'status.json',dict(stage='complete_for_available_runs'))
if __name__=='__main__': main()

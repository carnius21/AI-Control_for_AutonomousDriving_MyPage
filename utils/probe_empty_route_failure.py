"""Diagnostic interventions only; never training or policy performance results."""
import numpy as np
from utils import diagnose_n1_seeds as d

f = d.f
OUT = f.ROOT / 'results/empty_route_failure_probe'
EDGE = '170059994'


def run(policy, route, intervention):
    env = f.environment('N1', 11, 'none', [route])
    events = []
    changes = 0
    seen = False
    first = None
    try:
        obs, _ = env.reset(seed=40001, options={'route': route})
        while True:
            v = f.base.traci.vehicle
            edge = v.getRoadID(env.ego_id)
            lane = v.getLaneIndex(env.ego_id)
            speed = v.getSpeed(env.ego_id)
            remaining = f.base.traci.lane.getLength(v.getLaneID(env.ego_id)) - v.getLanePosition(env.ego_id)
            original = policy.predict(obs, deterministic=True)
            action = np.array(original, copy=True)
            if intervention == 'speed_only' and speed > 30 / 3.6:
                action[0] = -1
            if edge == EDGE:
                if first is None:
                    first = dict(t=env.step_count*env.step_length,lane=lane,speed=speed,remaining=remaining,nav=env.navigation_context())
                if intervention == 'correct_at_entry' and not seen:
                    action[1] = -1 if lane == 3 else 0
                    seen = True
                if intervention == 'correct_segment':
                    action[1] = -1 if lane == 3 else 0
                if intervention == 'correct_after_stop' and speed < .1 and remaining < 1 and not seen:
                    action[1] = -1
                    seen = True
            changed = not np.array_equal(action, original)
            changes += int(changed)
            before = dict(t=env.step_count*env.step_length,edge=edge,lane=lane,speed=speed,remaining=remaining,policy=original.tolist(),action=action.tolist())
            obs, _, done, cut, info = env.step(action)
            if edge == EDGE and (remaining > 1 or changed):
                before.update(command=info['lane_change'],accepted=info['lane_change_applied'],after_lane=v.getLaneIndex(env.ego_id) if env.ego_id in v.getIDList() else None)
                events.append(before)
            if done or cut:
                result=dict(route=route,intervention=intervention,arrival=bool(info['arrived']),collision=bool(info['collided']),timeout=bool(cut and not done),seconds=env.step_count*env.step_length,modified_steps=changes,first=first,final=before,events=events)
                f.save(OUT/f'{route}-{intervention}.json',result)
                print(route,intervention,result['arrival'],result['seconds'],flush=True)
                return {k:v for k,v in result.items() if k!='events'}
    finally:
        env.close()


def main():
    f.base.torch.set_num_threads(1)
    OUT.mkdir(parents=True,exist_ok=True)
    policy=d.agent(11)
    rows=[]
    for route in ('route_03','route_04','route_13','route_14'):
        for treatment in ('baseline','speed_only','correct_at_entry','correct_after_stop','correct_segment'):
            rows.append(run(policy,route,treatment))
    f.save(OUT/'summary.json',rows)
    f.save(OUT/'manifest.json',dict(**f.stamp(),simulation_seed=40001,source_model_sha=f.base.digest(f.OUT/'runs/shared-N1-11/model.pt'),note='Deliberate diagnostic action interventions; NOT learned-policy success rates. No production settings modified.'))


if __name__=='__main__':
    main()

"""SUMO fixed-route counterfactual, separate from all policy evaluations."""
from utils.experiment_b import OUT, environment, save, traci
import numpy as np

def run():
    env=environment("none","B0",11,OUT/"probe")
    rows=[]
    try:
        for route in ("route_13","route_16"):
            for lane in (0,1):
                env.ego_depart_lane=str(lane)
                env.reset(seed=720011,options={"route":route})
                edge=env.snapshot[0]
                lane_id=f"{edge}_{lane}"
                traci.vehicle.moveTo(env.ego_id,lane_id,traci.lane.getLength(lane_id)-40)
                env._get_obs()
                row=dict(route=route,lane=lane,expected=env.routes[route][1],edges=[],holding_steps=0)
                for _ in range(180):
                    _,_,done,cut,info=env.step(np.array([0.5,0.],np.float32))
                    if env.snapshot:
                        road,actual_lane,_,_,_,_,_,speed,rem=env.snapshot
                        if not row["edges"] or row["edges"][-1]!=road:
                            row["edges"].append(road)
                        row["last"]=[road,actual_lane,speed,rem]
                        row["holding_steps"]+=int(road==edge and speed<=.1 and rem<=1)
                        if road!=edge and not road.startswith(":"):
                            break
                    if done or cut: break
                rows.append(row)
    finally:
        env.close()
    save(OUT/"sumo_route_probe.json",rows)

if __name__=="__main__":
    run()

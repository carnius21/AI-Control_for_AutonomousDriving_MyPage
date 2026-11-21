"""Compact terminal-event records for paired SUMO evaluations."""
from collections import deque
from utils.experiment_a import traci


class FailureLog:
    def __init__(self):
        self.moves = deque(maxlen=5)

    def before(self, env, obs):
        edge, lane, path, idx, j, distance, _, speed, remaining = env.snapshot
        nxt = path[idx+1] if idx+1 < len(path) else None
        targets = sorted(env.links.get(edge, {}).get(nxt, ()))
        prep = set()
        if j is not None:
            prep = set(env.links[path[j]][path[j+1]])
            for k in range(j-1, idx-1, -1):
                prep = {a for a,b in env.navigation.links[path[k],path[k+1]] if b in prep}
        leader = traci.vehicle.getLeader(env.ego_id,50)
        self.frame = dict(edge=edge,lane=lane,targets=targets,next_edge=nxt,
            remaining=round(remaining,1),speed=round(speed,2),leader=leader,
            split_distance=distance,split_index=j,prep=sorted(prep))
        self.near = {}
        for other in traci.lane.getLastStepVehicleIDs(traci.vehicle.getLaneID(env.ego_id)):
            if other != env.ego_id:
                delta=traci.vehicle.getLanePosition(other)-traci.vehicle.getLanePosition(env.ego_id)
                if abs(delta)<75:self.near[other]=delta

    def after(self,env,info,outcome=None):
        f=self.frame
        post=env.snapshot
        same_edge=post and post[0]==f["edge"]
        cmd=info["lane_change"]
        moved=bool(same_edge and post[1]!=f["lane"])
        # For a removed AV, SUMO no longer returns its post-impact lane.
        applied=bool(cmd and info["lane_change_applied"])
        toward=bool(f["prep"] and min(abs(g-f["lane"]-cmd) for g in f["prep"])<min(abs(g-f["lane"]) for g in f["prep"]))
        self.moves.append((applied or moved,toward and applied))
        if outcome not in ("collision","timeout"):return None
        note=dict(f,command=cmd,accel=round(info["accel_raw"],2))
        if outcome=="timeout" and post:
            edge,lane,path,k,_,_,_,speed,rem=post
            nxt=path[k+1] if k+1<len(path) else None
            targets=sorted(env.links.get(edge,{}).get(nxt,()))
            note.update(edge=edge,lane=lane,next_edge=nxt,targets=targets,remaining=round(rem,1),speed=round(speed,2))
            note["reason"]="incompatible_lane_end" if targets and lane not in targets and rem<=1 and speed<=.1 else "other"
        if outcome=="collision":
            crashes=[c for c in traci.simulation.getCollisions() if env.ego_id in (c.collider,c.victim)]
            note.update(kind="unknown",context="split_approach" if f["split_distance"] is not None and f["split_distance"]<=100 else "no_recent_change")
            if any(t for _,t in self.moves):note["context"]="toward_split"
            elif any(m for m,_ in self.moves):note["context"]="other_change"
            if crashes:
                c=crashes[0];other=c.victim if c.collider==env.ego_id else c.collider
                note.update(sumo_type=c.type,collision_lane=c.lane,partner=other,ego_collider=c.collider==env.ego_id)
                if c.type=="side":note["kind"]="side"
                elif c.type=="junction":note["kind"]="junction"
                elif c.type=="rear-end" or (c.type=="collision" and (other in self.near or (c.collider==env.ego_id and f["leader"] and f["leader"][0]==other))):
                    note["kind"]="ego_rear_ends" if c.collider==env.ego_id else "ego_hit_from_behind"
        return note


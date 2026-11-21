"""Experiment A: road-level navigation and reward ablations on jys2."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

os.environ["IC_LIBSUMO"] = "1"
import numpy as np
import torch
from gymnasium import spaces
from env.sumo_env import SumoHighwayEnv, traci
from env import ic_experiment as ic
from env.navigation_clarity import validity_features
from utils import mcw_train as m

ROOT = m.ROOT / "results" / "jys2_experiment_a_v1"
STAGES = ("none", "low", "high_real_ratio")
SIZE = 38
SENSOR_TRIALS = ("sensor200_pass","sensor200_step")
CONTINUATIONS = ("both_continue","both_risk", *SENSOR_TRIALS)
OBS_TRIALS = ("prep_validity", "prep_route_conn", "prep_both", *CONTINUATIONS)
VALIDITY_TRIALS = ("prep_validity", "prep_both", *CONTINUATIONS)
PREP_ARMS = ("A0_prep_only", *OBS_TRIALS)


def observation_size(arm):
    return SIZE + 2 * (arm in VALIDITY_TRIALS)



def directions(net, connections):
    """Rank outgoing roads by signed turn angle, independent of current lane."""
    vectors = {}
    for e in ET.parse(net).findall("edge"):
        if e.get("function"):
            continue
        points = [tuple(map(float,p.split(",")[:2])) for p in e.find("lane").get("shape").split()]
        def heading(a,b):
            return math.atan2(b[1]-a[1],b[0]-a[0])
        vectors[e.get("id")] = heading(points[0],points[min(3,len(points)-1)]), heading(points[max(-4,-len(points))],points[-1])
    choices = {}
    for src,dst,_,_ in connections:
        choices.setdefault(src,set()).add(dst)
    output = {}
    for src, exits in choices.items():
        if len(exits)<2:
            continue
        def angle(dst):
            delta = vectors[dst][0]-vectors[src][1]
            return math.atan2(math.sin(delta),math.cos(delta))
        for i,dst in enumerate(sorted(exits,key=angle)):
            output[src,dst] = 2*i/(len(exits)-1)-1
    return output


class RoadEnv(m.McwEnv):
    def reset(self,*args,**kwargs):
        self.decisions = {}
        self.events = Counter()
        self.last_dir = None
        self.trace = []
        return super().reset(*args,**kwargs)

    def split(self,path,idx,remaining):
        for j in range(idx,len(path)-1):
            src,dst = path[j:j+2]
            if remaining>400:
                break
            if (src,dst) in self.signs:
                return j,remaining
            remaining += self.navigation.link_lengths.get((src,dst),0)+self.navigation.lengths[dst]
        return None,None

    def _get_obs(self):
        v=traci.vehicle
        self.snapshot=None
        if self.ego_id not in v.getIDList():
            return np.zeros(observation_size(self.arm),np.float32)
        base=SumoHighwayEnv._get_obs(self)
        edge=v.getRoadID(self.ego_id)
        lane=v.getLaneIndex(self.ego_id)
        lid=v.getLaneID(self.ego_id)
        pos=v.getLanePosition(self.ego_id)
        speed=v.getSpeed(self.ego_id)
        path=v.getRoute(self.ego_id)
        idx=v.getRouteIndex(self.ego_id)
        rem=traci.lane.getLength(lid)-pos
        j,d=self.split(path,idx,rem) if not edge.startswith(":") else (None,None)
        sides={}
        for direction in (-1,1):
            front,rear=SumoHighwayEnv._scan_lane_neighbors(self,direction)
            sides[direction]=tuple(x if x and x[0]<=self.visibility else None for x in (front,rear))
        overlap=[float(any(x and x[0]<=0 for x in sides[k])) for k in (-1,1)]
        self.snapshot=(edge,lane,path,idx,j,d,sides,speed,rem)
        extra=[lane/max(1,self.counts.get(edge,1)-1), min(1,traci.lane.getMaxSpeed(lid)/self.vmax),
               float(edge in ic.RAMPS),self.signs[path[j],path[j+1]] if j is not None else 0,
               d/400 if d is not None else -1,*overlap]
        if self.arm in VALIDITY_TRIALS:
            extra.extend(validity_features(self.navigation_context()))
        return np.clip(np.asarray([*base,*extra],np.float32),-1,1)

    def step(self,action):
        edge,lane,path,idx,j,d,sides,v,rem=self.snapshot
        direction=self._quantize_lane_change(action[self.lane_change_index])
        risk=0.
        if direction:
            for k,other in enumerate(sides[direction]):
                if other:
                    gap,speed=other
                    closing=v-speed if k==0 else speed-v
                    if gap<=0:
                        risk=1.
                    elif closing>0:
                        risk=max(risk,1-gap/(2*closing))
        attempt=direction!=0 and (edge,lane,direction)!=self.last_dir and edge not in self.solid and 0<=lane+direction<self.counts.get(edge,0)
        self.last_dir=(edge,lane,direction) if direction else None
        if attempt:
            self.events["attempts"]+=1
            self.events["risk_attempts"]+=int(risk>0)
        if j is not None:
            src,dst=path[j:j+2]
            targets=set(self.links[src][dst])
            for k in range(j-1,idx-1,-1):
                targets={a for a,b in self.navigation.links[path[k],path[k+1]] if b in targets}
            eligible=bool(targets) and len(targets)<self.counts[edge]
            rec=self.decisions.setdefault(j,dict(start=d,secured=None,seen=False,eligible=False,passed=False))
            if not targets:
                rec["secured"]=None
            if "available" not in rec:
                start=j
                while start>0 and (path[start-1],path[start]) not in self.signs:
                    start-=1
                rec["available"]=sum(self.navigation.lengths[e] for e in path[start:j+1])+sum(self.navigation.link_lengths.get((path[k],path[k+1]),0.) for k in range(start,j))
            if eligible:
                rec["eligible"]=True
                if lane in targets:
                    if rec["secured"] is None:
                        rec["secured"]=d
                else:
                    rec["secured"]=None
                if rec["start"]>=300 and d<=300 and not rec["seen"]:
                    rec["seen"]=True
                    self.events["at300"]+=1
                    self.events["ready300"]+=int(lane in targets)
            self.last_wrong=eligible and idx==j and lane not in targets and rem<=10
        elif not edge.startswith(":"):
            self.last_wrong=False
        no_brake = False
        if self.arm == "both_risk" and v > 1 and action[self.accel_index] >= 0:
            lead = traci.vehicle.getLeader(self.ego_id, self.visibility)
            if lead and lead[0]:
                closing = v - traci.vehicle.getSpeed(lead[0])
                no_brake = closing > 0.5 and lead[1] < 2.5 * closing
        paid_before = len(self.credits.paid) if self.arm == "sensor200_step" else 0
        obs,reward,done,cut,info=super().step(action)
        if self.arm == "sensor200_step":
            levels = len(self.credits.paid) - paid_before
            if levels:
                self.training_totals["prep_payments"] += levels
                self.training_totals["prep_reward"] += 0.1 * levels
                self.events["prep_payments"] += levels
                self.events["prep_reward"] += 0.1 * levels
        extra=0.
        if no_brake and not done:
            extra -= 0.15
            self.training_totals["no_brake_steps"] += 1
            self.events["no_brake_steps"] += 1
        post=self.snapshot
        if post and not post[0].startswith(":"):
            for key,rec in self.decisions.items():
                if not rec["passed"] and post[3]==key+1 and post[0]==path[key+1]:
                    rec["passed"]=True
                    self.events["passes"]+=1
                    if self.arm in ("A1","A2","A4"):
                        extra+=0.5
                    if self.arm != "sensor200_step" and self.arm in ("A2","A4",*PREP_ARMS) and rec["eligible"] and rec["secured"] is not None:
                        bonus=.25*min(1,rec["secured"]/max(1,min(300,rec["available"])))
                        extra+=bonus
                        self.events["prep_reward"]+=bonus
                        if self.arm in PREP_ARMS and bonus > 0:
                            self.events["prep_payments"] += 1
                            self.training_totals["prep_payments"] += 1
                            self.training_totals["prep_reward"] += bonus
        if self.arm == "A0_missed_split" and post and not info["collided"]:
            actual, current_lane, _, current_idx, _, _, _, speed, remaining = post
            for key, rec in self.decisions.items():
                if rec["passed"] or rec.get("missed"):
                    continue
                wrong_exit = (not actual.startswith(":") and current_idx == key + 1
                              and actual != path[key + 1])
                stranded = (cut and actual == path[key] and current_idx == key
                            and remaining <= 0.5 and speed <= 0.1
                            and current_lane not in self.links[actual][path[key + 1]])
                if wrong_exit or stranded:
                    rec["missed"] = True
                    self.events["missed_split_penalties"] += 1
                    extra -= 1.0
        if not done and attempt and self.arm in ("A3","A4"):
            extra-=.1*risk
        if self.arm in (*PREP_ARMS,"A0_restart_control") and self.episode_route == "route_16":
            if edge == "86198728":
                self.events["split16_left_requests"] += int(direction == 1)
                if post and post[0] == edge and post[1] > lane:
                    self.events["split16_actual_left"] += 1
                    if lane == 0 and post[1] in self.links[edge][path[idx+1]]:
                        self.events.setdefault("split16_first_correct_move_m",round(rem,1))
                if direction == 1 and sides[1] == (None, None):
                    self.events[f"split16_left_both_gaps_clear_{self.visibility:g}m"] += 1
            if post and post[0] == "86198725":
                self.events["split16_passed"] = 1
        if self.record and info["collided"]:
            self.events["collision_unknown"]+=1
            for crash in traci.simulation.getCollisions():
                if self.ego_id not in (crash.collider,crash.victim):
                    continue
                if crash.type in ("rear-end","side"):
                    self.events["collision_unknown"]-=1
                    self.events["collision_"+crash.type]+=1
                    break
        if self.record and j is not None:
            self.trace.append((self.step_count,edge,lane,round(d,1),round(v,2),sides,float(action[self.accel_index]),direction,info["lane_change_applied"],info["lane_after"],round(post[7],2) if post else None))
        return obs,reward+extra,done,cut,info


def make(stage,arm,seed,folder):
    cfg=m.prepare_scenario(stage,folder)
    road,nav=m.load_network_metadata(cfg.parent/"network.net.xml",cfg.parent/"highway.rou.xml")
    a=argparse.Namespace(stage=stage,safety=False,prep_reward=False,smoke=False,min_front_gap=3.5,
        min_rear_gap=3.5,rear_tau=.35,approach_horizon=1.2,collision_penalty=15,arrival_bonus=5,
        lc_penalty=0.0)
    action,reward,sim,ego,traffic=m.build_configs(a)
    ego["depart_lane"]="0"
    sensor_obs = dict(m.OBSERVATION, visibility=200.0) if arm in SENSOR_TRIALS else m.OBSERVATION
    env=RoadEnv(str(cfg),road,ego,sim,sensor_obs,action,reward,traffic,(),seed,
        navigation=nav,clarity="baseline",route_conn=arm in ("prep_route_conn","prep_both",*CONTINUATIONS),prep_reward=(arm == "sensor200_step"))
    env.training_totals=Counter()
    env.signs=directions(cfg.parent/"network.net.xml",road["connections"])
    env.arm,env.record,env.last_wrong=arm,False,False
    env.observation_space=spaces.Box(-1,1,(observation_size(arm),),np.float32)
    return env


def preflight():
    env=make("none","A0",11,ROOT/"checks")
    details={}
    try:
        for route in ("route_04","route_14"):
            obs,_=env.reset(options={"route":route})
            path=env.routes[route]
            splits=[(a,b,env.signs[a,b]) for a,b in zip(path,path[1:]) if (a,b) in env.signs]
            assert len(splits)>=2 and obs.shape==(SIZE,)
            assert all(len({env.signs[a,c] for c in env.links[a]})==len(env.links[a]) for a,b,_ in splits)
            details[route]=splits
        v=traci.vehicle
        edge=v.getRoadID(env.ego_id)
        assert env.counts[edge]>1
        def place(car,lane,pos):
            v.moveTo(car,f"{edge}_{lane}",pos)
        place(env.ego_id,0,100)
        assert env._get_obs()[-1]==0
        v.add("probe",route,typeID="ego_type",departLane="1")
        traci.simulationStep()
        place("probe",1,100)
        place(env.ego_id,0,100)
        assert env._get_obs()[-1]==1
        place("probe",1,85)
        v.setPreviousSpeed("probe",25)
        v.setPreviousSpeed(env.ego_id,10)
        assert env._get_obs()[-1]==0 and env.snapshot[6][1][1] is not None
        details["rear_gap_speed"]=env.snapshot[6][1][1]
        details["ego_speed"]=env.snapshot[7]
        assert details["rear_gap_speed"][1]>details["ego_speed"]
    finally:
        env.close()
    (ROOT/"preflight.json").write_text(json.dumps(details,indent=2))


if __name__=="__main__":
    preflight()



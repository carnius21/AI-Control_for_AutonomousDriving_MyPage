"""Static-map navigation observations. Never changes actions or safety rules."""
from collections import defaultdict
import numpy as np
from env.ic_experiment import ICExperimentEnv
from env.sumo_env import traci

class RouteNavigation:
    def __init__(self, counts, connections, lengths, horizon=300., link_lengths=None):
        self.counts, self.lengths, self.horizon = counts, lengths, horizon
        self.links = defaultdict(list)
        for src,dst,a,b in connections:self.links[src,dst].append((a,b))
        self.link_lengths = link_lengths or {}

    @staticmethod
    def offset(lane, targets):
        return min(targets,key=lambda x:(abs(x-lane),x))-lane if targets else 0

    def query(self,path,index,lane,remaining,internal=False):
        empty=dict(current_targets=[],prepare_targets=[],distance=None,decision_edge=None,ambiguous=False)
        if internal or index<0 or index+1>=len(path):return empty
        src=path[index]
        current={a for a,b in self.links[src,path[index+1]]}
        result=dict(empty,current_targets=sorted(current))
        distance=max(0.,remaining)
        for j in range(index,len(path)-1):
            edge,nxt=path[j:j+2]
            if distance>self.horizon:break
            targets={a for a,b in self.links[edge,nxt]}
            if targets and len(targets)<self.counts[edge]:
                # Back-project actual lane links; never compare lane numbers across edges.
                projected=targets
                for k in range(j-1,index-1,-1):
                    projected={a for a,b in self.links[path[k],path[k+1]] if b in projected}
                result.update(prepare_targets=sorted(projected),distance=distance,decision_edge=edge,ambiguous=not bool(projected))
                return result
            distance+=self.link_lengths.get((edge,nxt),0.)+self.lengths[nxt]
        return result

class NavigationEnv(ICExperimentEnv):
    def __init__(self,*args,observation_mode='N0',navigation=None,**kwargs):
        assert observation_mode in ('N0','N1','N2')
        self.observation_mode=observation_mode;self.navigation=navigation
        self.action_checks=0;self.route_override_count=0;self.episode_seeds=[]
        super().__init__(*args,**kwargs)

    def reset(self,seed=None,options=None):
        result=super().reset(seed=seed,options=options)
        self.episode_seeds.append(self.sumo_seed)
        return result

    def navigation_context(self):
        v=traci.vehicle;e=v.getRoadID(self.ego_id)
        return self.navigation.query(self.routes[self.episode_route],v.getRouteIndex(self.ego_id),v.getLaneIndex(self.ego_id),traci.lane.getLength(v.getLaneID(self.ego_id))-v.getLanePosition(self.ego_id),e.startswith(':'))

    def _get_obs(self):
        obs=super()._get_obs()
        if self.observation_mode=='N0' or self.ego_id not in traci.vehicle.getIDList():return obs
        nav=self.navigation_context();lane=traci.vehicle.getLaneIndex(self.ego_id)
        obs[-6:-3]=[np.clip(self.navigation.offset(lane,nav['current_targets'])/3,-1,1),nav['distance']/self.navigation.horizon if nav['distance'] is not None else -1,np.clip(self.navigation.offset(lane,nav['prepare_targets'])/3,-1,1)]
        assert obs.shape==(37,) and np.isfinite(obs).all() and np.max(np.abs(obs))<=1.00001
        return obs

    def _lane_connectivity(self,offset):
        value=super()._lane_connectivity(offset)
        if self.observation_mode!='N2' or value<0:return value
        nav=self.navigation_context()
        if not nav['current_targets']:return value
        v=traci.vehicle;lane=v.getLaneIndex(self.ego_id)+offset
        if lane in nav['current_targets']:return value
        remaining=traci.lane.getLength(v.getRoadID(self.ego_id)+'_'+str(lane))-v.getLanePosition(self.ego_id)
        return float(np.clip(remaining/self.visibility,0,1))

    def step(self,action):
        # Pass the very same policy action through the unchanged parent environment.
        original=np.asarray(action).copy()
        obs,r,done,cut,info=super().step(action)
        assert np.array_equal(original,np.asarray(action))
        assert np.isclose(info['lane_change_raw'],np.clip(original[self.lane_change_index],-1,1))
        assert np.isclose(info['accel_raw'],np.clip(original[self.accel_index],-1,1))
        self.action_checks+=1
        info['policy_action_raw']=original.tolist();info['environment_action_raw']=original.tolist()
        info['route_override_count']=self.route_override_count
        return obs,r,done,cut,info

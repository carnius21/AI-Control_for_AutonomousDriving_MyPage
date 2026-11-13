"""Reproduce timeout cross-episode leakage without modifying training code."""
import json
from pathlib import Path
from utils.buffer import RolloutBuffer


def target(next_episode_reward, boundary):
    buffer=RolloutBuffer()
    # Matches PPO: timeout reward already includes gamma * terminal-state value.
    buffer.add([0],[0,0],0,0+.99*4,2,boundary)
    buffer.add([1],[0,0],0,next_episode_reward,0,True)
    _,returns=buffer.compute_gae(0,.99,.95)
    return float(returns[0])


def main():
    observed=[target(r,False) for r in (0,100)]
    isolated=[target(r,True) for r in (0,100)]
    assert abs(observed[1]-observed[0])>90
    assert abs(isolated[1]-isolated[0])<1e-6
    result=dict(current_targets=observed,boundary_isolated_targets=isolated,expected=3.96,next_episode_rewards=[0,100],note='Synthetic reproduction of current PPO timeout storage plus actual RolloutBuffer.compute_gae. Not a training fix or proof of measured performance impact.')
    out=Path(__file__).resolve().parents[1]/'results/navigation_clarity_checkpoints_v1/timeout-bootstrap-probe.json'
    out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':main()

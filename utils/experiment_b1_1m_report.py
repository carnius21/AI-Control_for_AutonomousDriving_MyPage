"""Compare frozen B1 policies on the same held-out road, traffic, and start cases."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import csv

from utils.experiment_b1_1m import OUT, SEEDS, STAGES, PAIRS, HOLD
from utils.experiment_b_eval import score


def run():
    rows=[]
    scenes=[]
    for seed in SEEDS:
        directory=OUT/f"B1_{seed}"
        best=json.loads((directory/"selection.json").read_text())["selected"]
        for stage in STAGES:
            baseline={}
            for model,step in (("60만",600000),("100만",1000000),("선정",best)):
                episodes=json.loads((directory/f"hold_{step}_{stage}.json").read_text())
                starts={(x["route"],x["sim_seed"]):x["start"] for x in episodes}
                assert len(starts)==len(episodes)==128 and {s for _,s in starts}=={b+l for b in HOLD for l in (0,1)}
                if baseline: assert baseline==starts
                else: baseline=starts
                passed,n,*_=score(episodes,PAIRS)
                counts=Counter(x["outcome"] for x in episodes)
                row=dict(seed=seed,stage=stage,model=model,step=step,pair=passed,pairs=n,runs=len(episodes),
                         arrival=counts["arrival"],collision=counts["collision"],timeout=counts["timeout"])
                assert sum(counts.values())==row["arrival"]+row["collision"]+row["timeout"]
                for route in ("route_13","route_16"):
                    for lane in (0,1):
                        group=[x for x in episodes if x["route"]==route and x["lane_case"]==lane]
                        assert len(group)==len(HOLD)
                        row[f"{route}_lane{lane}"]=sum(x["first"]["actual"]==x["first"]["expected"] for x in group)
                        if stage=="high_real_ratio" and model=="100만":
                            for x in group:
                                if x["first"]["actual"]!=x["first"]["expected"]:
                                    scenes.append(dict(seed=seed,**x))
                row["pair13_16"]=score(episodes,[p for p in PAIRS if p["exit"]=="route_13" and p["main"]=="route_16"])[0]
                rows.append(row)
    with (OUT/"summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (OUT/"high_13_16_failures.json").write_text(json.dumps(scenes,indent=2))
    return rows

if __name__=="__main__":
    run()

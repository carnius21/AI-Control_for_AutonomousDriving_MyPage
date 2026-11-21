"""Run the approved matched experiment series and retain its selection decisions."""
import concurrent.futures
import json
import subprocess
import sys
from collections import Counter

from utils.experiment_a import ROOT
from utils.run_experiment_a import save


def run(arm,seed=11,test=False):
    args=[sys.executable,"-X","utf8","-m","utils.run_experiment_a",arm,str(seed)]
    if test:
        args+=["--eval","600000","--holdout"]
    report=ROOT/f"{arm}_{seed}"/("holdout_600000.json" if test else "eval_600000.json")
    if not report.exists():
        suffix="_test" if test else ""
        with (ROOT/f"{arm}_{seed}{suffix}.log").open("ab") as log:
            subprocess.run(args,stdout=log,stderr=log,check=True)
    rows=json.loads(report.read_text())
    assert len(rows)==48 and len({(x["route"],x["seed"]) for x in rows})==48
    counts=Counter(x["outcome"] for x in rows)
    counts["wrong_timeout"]=sum(x["wrong_timeout"] for x in rows)
    for key in ("at300","ready300","risk_attempts","attempts"):
        counts[key]=sum(x["metrics"].get(key,0) for x in rows)
    return counts


def ratio(s,k,n):
    return s[k]/max(s[n],1)


def series():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        scores={"A0":run("A0")}
        futures={a:pool.submit(run,a) for a in ("A1","A3")}
        for a,f in futures.items():
            scores[a]=f.result()
        scores["A2"]=run("A2")
        a,b,c,d=[scores[k] for k in ("A0","A1","A2","A3")]
        prep=ratio(c,"ready300","at300")>ratio(b,"ready300","at300") and c["wrong_timeout"]<b["wrong_timeout"] and c["collision"]<=b["collision"]
        safe=d["collision"]<a["collision"] and d["timeout"]<=a["timeout"] and d["arrival"]>=a["arrival"]
        if prep and safe:
            scores["A4"]=run("A4")
        ranked=sorted(scores,key=lambda k:(-scores[k]["arrival"],scores[k]["collision"],scores[k]["wrong_timeout"]))
        # Include the best modified condition even if A0 wins, and its direct control.
        best=next(k for k in ranked if k!="A0")
        controls={"A1":"A0","A2":"A1","A3":"A0","A4":"A2"}
        selected=sorted({"A0",best,controls[best]})
        save(ROOT/"selection.json",dict(scores=scores,prep_improved=prep,safety_improved=safe,repeat=selected))
        for seed in (22,33):
            list(pool.map(lambda arm:run(arm,seed),selected))
        results={}
        for seed in (11,22,33):
            results[str(seed)]=dict(zip(selected,pool.map(lambda arm:run(arm,seed,True),selected)))
        save(ROOT/"holdout_summary.json",results)


if __name__=="__main__":
    series()

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

out = Path(__file__).resolve().parent
root = out.parent
jobs = [(a,s) for s in (11,22,33) for a in ("A1","A2","A3")]

def read_rows(arm,seed):
    rows=json.loads((root/f"{arm}_{seed}"/"eval_600000.json").read_text())
    keys=[(r["route"],r["seed"]) for r in rows]
    assert len(keys)==len(set(keys))==48
    return keys,dict(Counter(r["outcome"] for r in rows))

def run(job):
    arm,seed=job
    with (out/f"{arm}_{seed}.log").open("a") as log:
        subprocess.run([sys.executable,"-X","utf8","-u","-m","utils.run_experiment_a",arm,str(seed)],stdout=log,stderr=subprocess.STDOUT,check=True,creationflags=getattr(subprocess,"BELOW_NORMAL_PRIORITY_CLASS",0))
    keys,counts=read_rows(arm,seed)
    assert keys==read_rows("A0",seed)[0]
    return counts

def save(state):
    tmp=out/"summary.tmp"
    tmp.write_text(json.dumps(state,indent=2),encoding="utf-8")
    os.replace(tmp,out/"summary.json")

envfile=Path("utils/experiment_a.py")
assert "lc_penalty=0.0)" in envfile.read_text(encoding="utf-8")
state=dict(cost=0,steps=600000,stages=["none","low","high_real_ratio"],environment_sha256=hashlib.sha256(envfile.read_bytes()).hexdigest(),A0={s:read_rows("A0",s)[1] for s in (11,22,33)},completed={},errors={})
save(state)
with ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(run,j):j for j in jobs}
    for f in as_completed(futures):
        arm,seed=futures[f]
        key=f"{arm}_{seed}"
        try: state["completed"][key]=f.result()
        except Exception as e: state["errors"][key]=repr(e)
        save(state)
sys.exit(bool(state["errors"]))

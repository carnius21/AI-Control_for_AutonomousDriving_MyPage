import json,sys,subprocess
from pathlib import Path
from collections import Counter
out=Path(__file__).resolve().parent
summary={}
for seed in (11,22,33):
    arm="A0_no_lc_cost"
    with (out/f"seed{seed}.log").open("w") as log:
        status=subprocess.run([sys.executable,"-X","utf8","-u",str(out/"repeat.py"),arm,str(seed)],stdout=log,stderr=subprocess.STDOUT)
    status.check_returncode()
    rows=json.loads((out/f"{arm}_{seed}"/"eval_600000.json").read_text())
    assert len(rows)==len({(r["route"],r["seed"]) for r in rows})==48
    summary[seed]=Counter(r["outcome"] for r in rows)
    (out/"summary.json").write_text(json.dumps(summary,indent=2))

"""Build auditable checkpoint, route, matched-pair, and held-out tables."""
import csv
import itertools
import json
from collections import Counter, defaultdict
from utils.experiment_b import OUT, STEPS, STAGES, m
from utils.experiment_b_eval import score

def read(p):
    return json.loads(p.read_text())

def write_csv(name,rows):
    if not rows: return
    path=OUT/name
    tmp=path.with_suffix(".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)

def ratio(k,n):
    return round(100*k/n,2) if n else None

def measure(rows,exits,mains):
    out={"episodes":len(rows)}
    def add(key,k,n):
        out[key]=k
        out[key+"_n"]=n
        out[key+"_pct"]=ratio(k,n)
    for result in ("arrival","collision","timeout","other"):
        add(result,sum(r["outcome"]==result for r in rows),len(rows))
    for tag,routes in (("exit",exits),("main",mains),("first",set(m.ROUTES))):
        group=[r for r in rows if r["route"] in routes and r["first"]]
        correct=[r for r in group if r["first"]["actual"]==r["first"]["expected"]]
        wrong=[r for r in group if r["first"]["actual"] and r not in correct]
        add(tag+"_correct",len(correct),len(group))
        add(tag+"_wrong_road",len(wrong),len(group))
        for result in ("collision","timeout","other"):
            add(tag+"_before_"+result,sum(r["first"]["actual"] is None and r["outcome"]==result for r in group),len(group))
        for result in ("collision","timeout"):
            add(tag+"_after_"+result,sum(r["outcome"]==result for r in correct),len(group))
        for field in ("wrong_entries","returns","wrong_end_stops"):
            out[tag+"_"+field+"_events"]=sum(r["first"][field] for r in group)
            add(tag+"_"+field+"_episodes",sum(r["first"][field]>0 for r in group),len(group))
    return out


def report():
    pairs=read(OUT/"design.json")["pairs"]
    exits={p["exit"] for p in pairs}
    mains={p["main"] for p in pairs}
    summary=[]
    routes=[]
    pair_rows=[]
    failures=[]
    choices=[]
    for arm,seed in itertools.product(("B0","B1"),(11,22,33)):
        folder=OUT/f"{arm}_{seed}"
        selected=read(folder/"selection.json")["selected"] if (folder/"selection.json").exists() else None
        for prefix,step,stage in itertools.product(("select","hold"),STEPS,STAGES):
            file=folder/f"{prefix}_{step}_{stage}.json"
            if not file.exists(): continue
            rows=read(file)
            s=score(rows,pairs)
            key=dict(arm=arm,seed=seed,step=step,traffic=stage,partition=prefix)
            metrics=measure(rows,exits,mains)
            summary.append(dict(**key,**metrics,pair_correct=s[0],pair_n=s[1],pair_pct=ratio(*s[:2])))
            if prefix=="hold":
                for model,target in (("selected",selected),("final",600000)):
                    if step==target:
                        choices.append(dict(**summary[-1],model=model))
            bykey={(r["route"],r["sim_seed"]):r for r in rows}
            for p in pairs:
                for sim_seed in sorted({r["sim_seed"] for r in rows}):
                    a,b=[bykey[route,sim_seed]["first"] for route in (p["exit"],p["main"])]
                    pair_rows.append(dict(**key,exit=p["exit"],main=p["main"],sim_seed=sim_seed,
                        shared_lane=bool(set(p["main_lanes"])&set(p["exit_lanes"])),
                        exit_ready=a["initially_ready"],main_ready=b["initially_ready"],
                        both=a["actual"]==a["expected"] and b["actual"]==b["expected"]))
            for route in m.ROUTES:
                group=[r for r in rows if r["route"]==route]
                routes.append(dict(**key,route=route,**measure(group,exits,mains)))
                for r in group:
                    if r["outcome"]=="arrival" and (not r["first"] or r["first"]["expected"]==r["first"]["actual"]): continue
                    for k,item in r["forks"].items():
                        failures.append(dict(**key,route=route,sim_seed=r["sim_seed"],outcome=r["outcome"],fork=k,
                             expected=item["expected"],actual=item["actual"],wrong_entries=item["wrong_entries"],
                             returns=item["returns"],end_stops=item["wrong_end_stops"],last=json.dumps(r["last"]),
                             at_300=json.dumps(item["samples"]["300"]),at_100=json.dumps(item["samples"]["100"])))
    write_csv("checkpoint_metrics.csv",summary)
    write_csv("route_metrics.csv",routes)
    write_csv("pair_cases.csv",pair_rows)
    write_csv("failure_scenes.csv",failures)
    write_csv("holdout_metrics.csv",choices)
    lines=["# 실험 B", "",f"중간 평가 {sum(r['partition']=='select' for r in summary)} / 234개 조건. 고정 정책의 결정론적 주행을 평가했다.",
        "", "일치하는 초깃값에서 B0의 분기 통과 보상과 B1의 차로 변경 즉시 보상을 비교한다. 평가용 가중치 파일은 정책만 포함한다.",
        "고교통 중간 평가에서 경로 쌍 성공 건수, 완주 건수, 충돌이 적은 순서, 이른 체크포인트 순으로 시드별 대표 모델을 선정한다.",
        "경로 쌍은 3개 진입도로의 8개 조합이다. 같은 본선 경로가 여러 쌍에 쓰이므로 쌍별 결과는 통계적으로 독립적이지 않다. 13~15번과 16번은 본선·진출 연결 차로가 겹치지 않는다. 나머지 쌍은 0차로에서 두 도로가 모두 연결된다.",
        "무교통 13·16번 강제 유지 대조 주행에서 잘못된 차로는 180스텝 중 173스텝 동안 차로 끝에 섰다. 통과 후 실패는 분기 성공에 포함한다.",
        "진입·복귀·정지는 이벤트 수와 해당 이벤트를 한 번 이상 겪은 에피소드 비율로 구분한다. 처음부터 잘못된 차로에서 출발한 경우는 신규 진입에 포함하지 않는다.",
        "", "## 미사용 시드 검증", "", "|모델|보상|시드|스텝|교통|쌍 성공|정상 진출|본선 유지|완주|충돌|시간초과|","|---|---|---:|---:|---|---|---|---|---|---|---|"]
    for r in choices:
        def fmt(k):
            return f"{r[k]}/{r[k+'_n']} ({r[k+'_pct']}%)"
        lines.append(f"|{r['model']}|{r['arm']}|{r['seed']}|{r['step']}|{r['traffic']}|{r['pair_correct']}/{r['pair_n']} ({r['pair_pct']}%)|"+ "|".join(fmt(k) for k in ("exit_correct","main_correct","arrival","collision","timeout"))+"|")
    if len(choices)==36:
        lines.extend(["","## 고교통 판정",""])
        for model in ("selected","final"):
            pooled={}
            for arm in ("B0","B1"):
                group=[r for r in choices if r["model"]==model and r["arm"]==arm and r["traffic"]=="high_real_ratio"]
                n=sum(r["episodes"] for r in group)
                total=lambda k:sum(r[k] for r in group)
                pooled[arm]={k:ratio(total(k),total(k+"_n")) for k in ("exit_correct","main_correct","main_wrong_road","exit_wrong_road","collision")}
                cp=ratio(total("collision"),n)
                resolved=ratio(total("arrival")+total("collision"),n)
                lines.append(f"- {model} {arm} · 쌍 {total('pair_correct')}/{total('pair_n')}, 완주+충돌 {resolved}% (목표와 {100-resolved:.2f}%p 차이), 충돌 {cp}% (5% 미만 {'달성' if cp<5 else '미달'}).")
            deltas={k:round(pooled['B1'][k]-pooled['B0'][k],2) for k in pooled['B0']}
            lines.append(f"- {model} B1−B0 차이(%p) · 진출 {deltas['exit_correct']:+}, 본선 유지 {deltas['main_correct']:+}, 본선의 오진출 {deltas['main_wrong_road']:+}, 진출 경로의 본선 진입 {deltas['exit_wrong_road']:+}, 충돌 {deltas['collision']:+}. 지급 시점과 크기를 함께 바꾼 비교이다.")
        lines.extend(["","## 교통 수준에 따른 실패",""])
        patterns=[]
        for arm,seed in itertools.product(("B0","B1"),(11,22,33)):
            folder=OUT/f"{arm}_{seed}"
            for step in sorted({600000,read(folder/"selection.json")["selected"]}):
                groups=[{(r["route"],r["sim_seed"]):r for r in read(folder/f"hold_{step}_{t}.json")} for t in STAGES]
                for case,r in groups[0].items():
                    cases=[g[case] for g in groups]
                    if all(x["outcome"]=="arrival" for x in cases): continue
                    patterns.append(dict(arm=arm,seed=seed,step=step,route=case[0],sim_seed=case[1],**{t:x["outcome"] for t,x in zip(STAGES,cases)}, **{t+"_first":x["first"]["actual"] if x["first"] else None for t,x in zip(STAGES,cases)}))
                for idx,t in enumerate(STAGES):
                    count=sum(all(groups[j][c]["outcome"]=="arrival" for j in range(idx)) and groups[idx][c]["outcome"]!="arrival" for c in groups[idx])
                    lines.append(f"- {arm} 시드 {seed}, {step}스텝 · {t}에서 처음 완주 실패 {count}/{len(groups[idx])}.")
        write_csv("matched_traffic_failures.csv",patterns)
        lines.extend(["","## 13·16번 짝과 분기 접근 기록",""])
        for arm,seed in itertools.product(("B0","B1"),(11,22,33)):
            folder=OUT/f"{arm}_{seed}"
            best=read(folder/"selection.json")["selected"]
            for step in sorted({best,600000}):
                for stage in STAGES:
                    rows=read(folder/f"hold_{step}_{stage}.json")
                    route_pair=[p for p in pairs if (p["exit"],p["main"])==("route_13","route_16")]
                    count,n,*_=score(rows,route_pair)
                    lines.append(f"- {arm} 시드 {seed}, {step}스텝, {stage} · 13·16번 동시 성공 {count}/{n}.")
                    candidates=[r for r in rows if r["route"] in ("route_13","route_16") and r["first"]["actual"]!=r["first"]["expected"]]
                    if not candidates: continue
                    r=candidates[0]
                    scene=[]
                    for t,sample in r["first"]["samples"].items():
                        if isinstance(sample,str):
                            scene.append(f"{t}m {sample}")
                            continue
                        left,right=sample["adjacent"]["1"],sample["adjacent"]["-1"]
                        def gaps(pair):
                            return "/".join("미검출" if v is None else f"{v[0]:.1f}m" for v in pair)
                        scene.append(f"{sample['distance']:.1f}m에서 {sample['lane']}차로, 좌측 앞/뒤 {gaps(left)}, 우측 앞/뒤 {gaps(right)}, 가감속 {sample['accel']:.3f}, 차로 명령 {sample['command']}, 실제 차로 {sample['lane_after']}, 준비 보상 {sample['prep']:.3f}")
                    lines.append(f"  - {r['route']}, 교통 시드 {r['sim_seed']}, {r['outcome']}. "+" / ".join(scene)+f". 잘못된 차로 끝 정지 {r['first']['wrong_end_stops']}회.")
        pooled={arm:sum(r["pair_correct"] for r in choices if r["arm"]==arm and r["model"]=="selected" and r["traffic"]=="high_real_ratio") for arm in ("B0","B1")}
        winner="동률" if pooled["B0"]==pooled["B1"] else max(pooled,key=pooled.get)
        lines.extend(["","## 보상 비교","",f"미사용 시드 고교통에서 시드별 대표 체크포인트의 양쪽 경로 동시 성공 합계는 B0 {pooled['B0']}건, B1 {pooled['B1']}건이다. 관측한 성공 건수 기준 결과는 {winner}이다."])

    (OUT/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    report()

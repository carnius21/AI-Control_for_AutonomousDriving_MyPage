"""Render GitHub-ready results from completed runs; never infer unfinished outcomes."""
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/ic_campaign_v2"

def render():
    rows = sorted((OUT/"runs").glob("*/complete.json"))
    lines = ["# 퇴계원IC PPO 실험 결과", "",
             "평가를 마친 조건만 표시한다. 1만 스텝은 기능 점검이며, 본 실험은 조건별 20만 스텝이다.", "",
             "|조건|seed|학습 스텝|평가 에피소드|완주|충돌|시간 초과|기준 대비 완주/충돌|학습 시간(분)|",
             "|---|---:|---:|---:|---:|---:|---:|---|---:|"]
    results = [json.loads(p.read_text(encoding="utf8")) for p in rows]
    for p,r in zip(rows,results):
        evaluation=json.loads((p.parent/f"eval-{r['budget']}.json").read_text(encoding="utf8"))
        baseline=next((b for b in results if b["id"]==f"R0-{r['seed']}-{r['budget']}"),None)
        difference="—" if not baseline else " / ".join(f"{100*(r[k]-baseline[k]):+.1f}%p" for k in ("arrival","collision"))
        lines.append(f"|{r['id']}|{r['seed']}|{r['budget']:,}|{len(evaluation['rows'])}|{r['arrival']:.1%}|{r['collision']:.1%}|{r['timeout']:.1%}|{difference}|{r['training_seconds']/60:.1f}|")
    lines += ["", "지퍼 준수와 준비 성공률은 해당 사건만 분모로 사용한다. 해당 사건이 없으면 ‘관측 없음’으로 표시한다.",
              "", "|조건|100m 준비|지퍼 준수|램프 과속 시간 비율|최대 초과(km/h)|완주 평균(초)|",
              "|---|---:|---:|---:|---:|---:|"]
    def ratio(n, d):
        return f"{n}/{d} ({n/d:.1%})" if d else "관측 없음"
    for p,r in zip(rows,results):
        episodes=json.loads((p.parent/f"eval-{r['budget']}.json").read_text(encoding="utf8"))["rows"]
        def total(k):
            return sum(e[k] for e in episodes)
        times=[e["seconds"] for e in episodes if e["arrival"]]
        seconds=f"{mean(times):.1f}" if times else "완주 없음"
        lines.append(f"|{r['id']}|{ratio(total('ready'),total('prep'))}|{ratio(total('compliant'),total('zipper'))}|{ratio(total('over_steps'),total('ramp_steps'))}|{max(e['peak_excess_mps'] for e in episodes)*3.6:.1f}|{seconds}|")
    for p in rows:
        r=json.loads(p.read_text(encoding="utf8"))
        events=json.loads((p.parent/f"eval-{r['budget']}.json").read_text(encoding="utf8"))["rows"]
        lines+=["",f"<details><summary>{r['id']} 경로별 평가</summary>", "",
                "|경로|횟수|완주|충돌|시간 초과|","|---|---:|---:|---:|---:|"]
        for route in sorted({e["route"] for e in events}):
            group=[e for e in events if e["route"]==route]
            lines.append(f"|{route}|{len(group)}|{mean(e['arrival'] for e in group):.1%}|{mean(e['collision'] for e in group):.1%}|{mean(e['timeout'] for e in group):.1%}|")
        lines+=["","</details>"]
    return "\n".join(lines)+"\n"

if __name__=="__main__":
    (ROOT/"docs/ic-ppo-results.md").write_text(render(),encoding="utf8")
    from torch.utils.tensorboard import SummaryWriter
    for folder in (OUT/"runs").glob("*"):
        for result in folder.glob("eval-*.json"):
            # One evaluation event file per checkpoint, so repeated exports do not duplicate points.
            target=folder/"tb"
            marker=folder/(result.stem+".exported")
            if marker.exists(): continue
            data=json.loads(result.read_text(encoding="utf8"))
            with SummaryWriter(str(target)) as writer:
                for key,value in data["rates"].items():
                    writer.add_scalar("eval/"+key,value,data["step"])
            marker.touch()

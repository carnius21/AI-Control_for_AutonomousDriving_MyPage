"""Audit natural HV turn signals and lane-change decisions at 0.2 s intervals."""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import statistics

import libsumo as sumo
from libsumo import constants as tc

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/neighbor_fix_20261114/inputs/reference"
OUT = ROOT / "results/hv_blinker_timeline_20261118"
SEEDS = (59101, 59102, 59103)
DT = 0.2
STEPS = 9000
DISTANCE = 50
WINDOW = 25
SIDES = ((1, 2, tc.LCA_LEFT, tc.LCA_BLOCKED_LEFT), (-1, 1, tc.LCA_RIGHT, tc.LCA_BLOCKED_RIGHT))


def run(seed):
    sumo.start(["sumo", "-c", str(SOURCE / "run.sumocfg"), "--seed", str(seed),
                "--step-length", str(DT), "--no-step-log", "true", "--no-warnings", "true"])
    previous = {}
    neighbor_since = {}
    episodes = {}
    records = []
    counts = Counter()
    edge_lanes = {}
    version = sumo.getVersion()

    def finish(key, step, outcome):
        record = episodes.pop(key)
        record.update(end_step=step, outcome=outcome)
        records.append(record)

    try:
        for step in range(1, STEPS + 1):
            sumo.simulationStep()
            counts["av_present_steps"] += int("ego" in sumo.vehicle.getIDList())
            v = sumo.vehicle
            snapshot = {i: (v.getRoadID(i), v.getLaneIndex(i), v.getLanePosition(i), v.getSignals(i))
                        for i in v.getIDList()}
            lanes = defaultdict(list)
            for i, (edge, lane, position, _) in snapshot.items():
                if not edge.startswith(":"):
                    lanes[edge, lane].append((position, i))
            for vehicles in lanes.values():
                vehicles.sort()

            for key in episodes.keys() - {(i, direction) for i in snapshot for direction in (-1, 1)}:
                finish(key, step, "vehicle_left")
            current = {}
            current_since = {}
            for i, (edge, lane, pos, signals) in snapshot.items():
                old = previous.get(i)
                same_edge = old is not None and old[0] == edge and not edge.startswith(":")
                changed = same_edge and old[1] != lane
                if changed:
                    counts["changes"] += 1
                    bit = 2 if lane > old[1] else 1
                    counts["prior_signal"] += int(bool(old[2] & bit))
                contexts = {}
                if not edge.startswith(":") and edge not in edge_lanes:
                    edge_lanes[edge] = sumo.edge.getLaneNumber(edge)
                for direction, signal_bit, intent_bit, neighbor_mask in SIDES:
                    key = (i, direction)
                    if key in episodes and (changed or not same_edge or not signals & signal_bit):
                        outcome = ("matching_change" if changed and (lane-old[1])*direction > 0
                                   else "other_change" if changed else "edge_changed" if not same_edge
                                   else "signal_off")
                        finish(key, step, outcome)
                    if edge.startswith(":") or not 0 <= lane+direction < edge_lanes[edge]:
                        continue
                    vehicles = lanes.get((edge, lane+direction), [])
                    lo = bisect_left(vehicles, (pos-DISTANCE, ""))
                    hi = bisect_right(vehicles, (pos+DISTANCE, chr(0x10ffff)))
                    nearby = {other: round(other_pos-pos, 2) for other_pos, other in vehicles[lo:hi]}
                    same_lane = same_edge and old[1] == lane
                    before = old[3].get(direction) if same_lane else None
                    since = neighbor_since.get(key, {}) if before is not None else {}
                    current_since[key] = {other: since.get(other, step) for other in nearby}
                    state = v.getLaneChangeState(i, direction)[0]
                    blocked = state != tc.LCA_UNKNOWN and bool(state & intent_bit and state & neighbor_mask)
                    context = dict(step=step, state=state, neighbor_blocked=blocked, neighbors=nearby)
                    contexts[direction] = context
                    onset = before is not None and not old[2] & signal_bit and signals & signal_bit
                    if onset and key not in episodes:
                        episodes[key] = dict(seed=seed, vehicle=i, edge=edge, lane=lane,
                            direction=direction, onset_step=step, before=before, onset=context,
                            neighbor_entry_steps={other: first for other, first in current_since[key].items()
                                                  if step-first <= WINDOW},
                            both_signals=(signals & 3) == 3, after=None)
                    if key in episodes:
                        record = episodes[key]
                        if step == record["onset_step"]+1:
                            record["after"] = context
                        if context["neighbor_blocked"]:
                            record.setdefault("first_blocked_step", step)
                            record["last_blocked_step"] = step
                        record["last_on"] = context
                current[i] = edge, lane, signals, contexts
            previous, neighbor_since = current, current_since
            if step % 3000 == 0:
                print(f"{seed} {step*DT:.0f}s {counts['changes']} changes", flush=True)
        for key in list(episodes):
            finish(key, STEPS, "end_of_run")
    finally:
        sumo.close()
    result = dict(seed=seed, version=version, counts=dict(counts), events=records)
    with gzip.open(OUT / f"{seed}.json.gz", "wt", encoding="utf8") as file:
        json.dump(result, file)
    return result


def summarize(results):
    events = [e for r in results for e in r["events"] if not e["both_signals"]]
    group = [e for e in events if e["outcome"] == "matching_change"]

    def entered_at_onset(event):
        return event["onset_step"] in event["neighbor_entry_steps"].values()

    def describe(sample):
        n = len(sample)
        first_neighbor = [e for e in sample if entered_at_onset(e) and not e["before"]["neighbors"]]
        return dict(n=n,
            blocked_at_onset=sum(e["onset"]["neighbor_blocked"] for e in sample),
            blocked_one_step_before=sum(e["before"]["neighbor_blocked"] for e in sample),
            blocked_after_onset=sum("first_blocked_step" in e for e in sample),
            new_neighbor_at_onset=sum(entered_at_onset(e) for e in sample),
            previously_empty_at_onset=len(first_neighbor),
            previously_empty_then_change_one_step=sum(
                e["outcome"] == "matching_change" and e["end_step"] == e["onset_step"] + 1
                for e in first_neighbor),
            new_neighbor_recent=sum(bool(e["neighbor_entry_steps"]) for e in sample),
            no_neighbor_at_onset=sum(not e["onset"]["neighbors"] for e in sample),
            unknown_at_onset=sum(e["onset"]["state"] == tc.LCA_UNKNOWN for e in sample))
    times = [(e["end_step"]-e["onset_step"])*DT for e in group]
    report = dict(runs=[{k:v for k,v in r.items() if k!="events"} for r in results],
        outcomes=dict(Counter(e["outcome"] for e in events)), all_onsets=describe(events),
        followed_by_change=describe(group), without_change=describe([e for e in events if e["outcome"]!="matching_change"]),
        matching_onset_seconds=dict(median=statistics.median(times),mean=statistics.mean(times),
            max=max(times), after_one_step=sum(e["end_step"] == e["onset_step"]+1 for e in group)))
    (OUT / "summary.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=len(SEEDS)) as pool:
        summarize(list(pool.map(run, SEEDS)))


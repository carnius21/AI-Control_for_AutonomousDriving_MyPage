"""Compare combined rewards, magnitude, and leave-one-out effects on paired cases."""
import json

from utils.ic_campaign import OUT, save, torch, train_run


def main():
    torch.set_num_threads(1)
    folder = OUT / "combination-trials"
    conditions = {
        "COMBO": ("ROUTE100", "ZIP", "RAMP"),
        "COMBO025": ("ROUTE100", "ZIP", "RAMP", "SCALE025"),
    }
    results = {}

    def run(name, variants, seed):
        save(folder / "status.json", dict(condition=name, seed=seed, stage="running"))
        result = train_run(name, variants, seed, 200000, final_only=True)
        results[f"{name}-{seed}"] = result
        save(folder / "results.json", results)
        return result

    for name, variants in conditions.items():
        run(name, variants, 11)
    # Compare both safety and completion. Probe individual contributions whenever
    # either metric deteriorates relative to the paired baseline.
    baseline = json.loads((OUT / "runs/R0-11-200000/complete.json").read_text())
    for name, variants in list(conditions.items()):
        result = results[f"{name}-11"]
        if result["arrival"] < baseline["arrival"] or result["collision"] > baseline["collision"]:
            for term in ("ROUTE100", "ZIP", "RAMP"):
                run(f"{name}-NO-{term}", tuple(v for v in variants if v != term), 11)
    for seed in (22, 33):
        for name, variants in conditions.items():
            run(name, variants, seed)
    save(folder / "status.json", dict(stage="complete", runs=list(results)))


if __name__ == "__main__":
    main()

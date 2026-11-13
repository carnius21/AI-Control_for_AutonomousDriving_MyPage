"""Run the independent follow-up experiments on the frozen baseline evaluation cases."""
import json

from utils.ic_campaign import HPARAMS, OUT, PPO, environment, evaluate, rates, save, torch, train_run


def main():
    torch.set_num_threads(1)
    baseline = OUT / "runs/R0-11-200000"
    env = environment((), 11)
    agent = PPO(obs_dim=env.obs_dim, act_dim=env.act_dim, **dict(HPARAMS, device="cpu"))
    env.close()
    agent.load(str(baseline / "policy-200000.pt"))
    original = json.loads((baseline / "eval-200000.json").read_text())["rows"]
    for name, variants in (("reference", ("MEASURE_ROUTE",)), ("first-second", ("MEASURE_ROUTE", "START1"))):
        target = OUT / "failure-trials" / (name + ".json")
        if target.exists():
            continue
        rows = evaluate(agent, variants, range(1001, 1006), ["base"])
        if name == "reference":
            for new, old in zip(rows, original, strict=True):
                if any(new[k] != old[k] for k in old):
                    raise RuntimeError("Baseline replay differs from the recorded evaluation")
        save(target, dict(checkpoint="R0-11-200000/policy-200000.pt", rates=rates(rows), rows=rows))
    train_run("ROUTE100", ("ROUTE100",), 11, 200000)


if __name__ == "__main__":
    main()

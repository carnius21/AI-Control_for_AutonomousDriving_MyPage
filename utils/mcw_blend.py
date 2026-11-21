"""Reproduce or verify the blended mcw2_nosafety_final policy checkpoint."""
import argparse
import hashlib
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blend_checkpoints(v1_path: Path, v2_path: Path, alpha: float) -> dict:
    sd1 = torch.load(str(v1_path), map_location="cpu")
    sd2 = torch.load(str(v2_path), map_location="cpu")
    if set(sd1.keys()) != set(sd2.keys()):
        raise ValueError("Checkpoint state_dict keys do not match")
    return {k: (1.0 - alpha) * sd1[k] + alpha * sd2[k] for k in sd1}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v1", type=Path, default=Path("results/mcw_runs/mcw2_v5b_high_real_ratio_dagger/best_model.pt"))
    p.add_argument("--v2", type=Path, default=Path("results/mcw_runs/mcw2_v5b_high_real_ratio_dagger_v2/best_model.pt"))
    p.add_argument("--alpha", type=float, default=0.20, help="Weight on v2: (1-alpha)*v1 + alpha*v2")
    p.add_argument("--out", type=Path, default=Path("results/mcw_runs/mcw2_nosafety_final/best_model.pt"))
    p.add_argument("--verify-only", action="store_true", help="Check that --out matches the blended tensors")
    args = p.parse_args()

    blended = blend_checkpoints(args.v1, args.v2, args.alpha)
    if args.verify_only:
        existing = torch.load(str(args.out), map_location="cpu")
        max_diff = max(float((blended[k] - existing[k]).abs().max().item()) for k in blended)
        print(f"[VERIFY] max_abs_diff={max_diff:.3e}  target_sha256={sha256(args.out)}")
        if max_diff > 1e-6:
            raise SystemExit(1)
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(blended, str(args.out))
    print(f"[SAVED] {args.out}  alpha={args.alpha}  sha256={sha256(args.out)}")


if __name__ == "__main__":
    main()

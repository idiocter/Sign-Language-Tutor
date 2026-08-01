"""Generate a SYNTHETIC NSL landmark dataset so Phase 1 runs before real data exists.

Real NSL data does not exist publicly — you collect it with signers (DOWNLOADS.md). Until
then, this fabricates separable landmark sequences with realistic structure:

  * each sign has a latent resting pose + a movement direction,
  * each signer adds a consistent style offset (so held-out-signer eval is meaningful),
  * each take adds noise and a temporal ramp.

Output matches the capture tool exactly — normalized ``(SEQ_LEN, FEATURE_DIM)`` arrays at
``data/raw/<sign>/<sign>__<signer>__<stamp>.npy`` — so preprocessing.discover and
split_by_signer consume it unchanged.

    python scripts/synth_data.py --signs 40 --signers 8 --takes 12 --clean

THIS IS NOT REAL DATA. Any accuracy reported on it measures the pipeline, not NSL
recognition. Delete data/raw and collect real signs before trusting a number.
"""

from __future__ import annotations

import argparse
import shutil

import numpy as np

from signbridge.config import FEATURE_DIM, RAW_DIR, SEQ_LEN
from signbridge.vocabulary import build_dictionary


def _sign_latents(sign_ids: list[str], seed: int):
    # Tighter class spacing so signs aren't trivially separable.
    rng = np.random.default_rng(seed)
    poses = rng.normal(0.0, 0.35, size=(len(sign_ids), FEATURE_DIM)).astype(np.float32)
    moves = rng.normal(0.0, 0.22, size=(len(sign_ids), FEATURE_DIM)).astype(np.float32)
    return poses, moves


def _signer_styles(n_signers: int, sigma: float, seed: int):
    """Each signer gets a pose offset AND a multiplicative movement gain.

    The gain is the important part: a per-signer distortion of *movement* (not just a
    constant offset) is what makes held-out-signer generalization genuinely hard — a
    constant offset alone leaves the discriminative signal untouched.
    """
    rng = np.random.default_rng(seed + 777)
    offsets = rng.normal(0.0, sigma, size=(n_signers, FEATURE_DIM)).astype(np.float32)
    gains = rng.normal(1.0, 0.35, size=(n_signers, FEATURE_DIM)).astype(np.float32)
    return offsets, gains


def _make_take(pose, move, signer_off, signer_gain, rng) -> np.ndarray:
    t = np.linspace(0.0, 1.0, SEQ_LEN, dtype=np.float32)
    ramp = np.sin(np.pi * t)[:, None]  # 0 -> 1 -> 0, the sign's motion arc
    amp = rng.uniform(0.75, 1.25)
    base = pose + signer_off + rng.normal(0.0, 0.04, size=FEATURE_DIM).astype(np.float32)
    eff_move = (amp * move) * signer_gain
    seq = base[None, :] + ramp * eff_move[None, :]
    seq += rng.normal(0.0, 0.09, size=seq.shape).astype(np.float32)  # per-frame jitter
    return seq.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signs", type=int, default=40, help="number of signs (from vocabulary)")
    ap.add_argument("--signers", type=int, default=8)
    ap.add_argument("--takes", type=int, default=12, help="takes per (sign, signer)")
    ap.add_argument("--signer-sigma", type=float, default=0.18, help="signer style spread")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean", action="store_true", help="wipe data/raw first")
    args = ap.parse_args()

    if args.clean and RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    sign_ids = [s.sign_id for s in build_dictionary().signs][: args.signs]
    poses, moves = _sign_latents(sign_ids, args.seed)
    offsets, gains = _signer_styles(args.signers, args.signer_sigma, args.seed)
    signer_ids = [f"S{n + 1:02d}" for n in range(args.signers)]

    rng = np.random.default_rng(args.seed + 1)
    total = 0
    for si, sign_id in enumerate(sign_ids):
        out = RAW_DIR / sign_id
        out.mkdir(parents=True, exist_ok=True)
        for gi, signer in enumerate(signer_ids):
            for take in range(args.takes):
                seq = _make_take(poses[si], moves[si], offsets[gi], gains[gi], rng)
                stamp = f"20260101_{total % 1_000_000:06d}"
                np.save(out / f"{sign_id}__{signer}__{stamp}.npy", seq)
                total += 1

    print(
        f"generated {total} synthetic takes: {len(sign_ids)} signs x "
        f"{args.signers} signers x {args.takes} takes -> {RAW_DIR}"
    )
    print("NOTE: synthetic data. Replace with real collected signs before trusting metrics.")


if __name__ == "__main__":
    main()

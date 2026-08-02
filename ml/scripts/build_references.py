"""Build per-sign reference sequences for DTW scoring (Phase 3).

The tutor scores a learner's attempt against a *reference* rendition of each sign
(TECH_STACK.md Layer 6: DTW on normalized joint angles). This computes a reference as the
per-sign mean of the collected normalized takes and writes one `.npy` per sign.

    python scripts/build_references.py

Writes ml/data/refs/<sign>.npy and copies them to api/models/references/ so the backend can
score without touching the raw dataset. On synthetic data these references are synthetic —
regenerate once real signs are collected; the ideal reference is a native signer's take,
not a mean.
"""

from __future__ import annotations

import shutil
from collections import defaultdict

import numpy as np

from signbridge.config import ML_ROOT, REFS_DIR
from signbridge.preprocessing import discover

API_REF_DIR = ML_ROOT.parent / "api" / "models" / "references"


def main() -> None:
    samples = discover()
    if not samples:
        raise SystemExit("No data in data/raw. Run scripts/synth_data.py first.")

    by_sign: dict[str, list] = defaultdict(list)
    for s in samples:
        by_sign[s.sign_id].append(s.path)

    REFS_DIR.mkdir(parents=True, exist_ok=True)
    API_REF_DIR.mkdir(parents=True, exist_ok=True)

    for sign_id, paths in sorted(by_sign.items()):
        ref = np.mean([np.load(p) for p in paths], axis=0).astype(np.float32)
        out = REFS_DIR / f"{sign_id}.npy"
        np.save(out, ref)
        shutil.copy(out, API_REF_DIR / f"{sign_id}.npy")

    print(f"wrote {len(by_sign)} references -> {REFS_DIR} (copied to {API_REF_DIR})")


if __name__ == "__main__":
    main()

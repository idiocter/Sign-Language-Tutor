"""Train the INTERIM linear recognition model and export it to ONNX.

Runs with only numpy + onnx (no torch), so the full Phase 1 loop — train, evaluate on
held-out *signers*, export, serve in the browser — works today on synthetic data.

    python scripts/synth_data.py --signs 40 --signers 8 --takes 12 --clean
    python scripts/train_lite.py

Reports **top-1 accuracy on held-out signers** — the Phase 1 exit metric (target ≥85%).
On synthetic data this measures the pipeline, not NSL recognition.

Artifacts written to ml/artifacts/ and copied to the web/ and api/ model dirs:
  model.onnx        the classifier graph
  labels.json       index -> sign_id
  prototypes.json   per-sign mean pooled feature (lets the demo synthesize an attempt)
  metrics.json      accuracy + provenance
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from signbridge.config import ML_ROOT
from signbridge.models.linear_model import INPUT_DIM, LinearSignClassifier, pool_features
from signbridge.preprocessing import discover, split_by_signer

ARTIFACTS = ML_ROOT / "artifacts"
WEB_MODEL_DIR = ML_ROOT.parent / "web" / "public" / "models" / "recognition"
API_MODEL_DIR = ML_ROOT.parent / "api" / "models" / "recognition"


def _load(samples) -> tuple[np.ndarray, np.ndarray]:
    feats, labels = [], []
    for s in samples:
        feats.append(pool_features(np.load(s.path)))
        labels.append(s.sign_id)
    return np.stack(feats), np.array(labels)


def main() -> None:
    samples = discover()
    if not samples:
        raise SystemExit("No data in data/raw. Run scripts/synth_data.py first.")

    split = split_by_signer(samples, seed=1)
    print("signers per split:", {k: sorted(v) for k, v in split.signer_sets().items()})

    Xtr, ytr_ids = _load(split.train)
    Xva, yva_ids = _load(split.val)
    Xte, yte_ids = _load(split.test)

    labels = sorted(set(ytr_ids) | set(yva_ids) | set(yte_ids))
    idx = {sid: i for i, sid in enumerate(labels)}
    ytr = np.array([idx[s] for s in ytr_ids])
    yva = np.array([idx[s] for s in yva_ids])
    yte = np.array([idx[s] for s in yte_ids])

    clf = LinearSignClassifier(labels).fit(Xtr, ytr, epochs=400, lr=0.5)
    acc_val = clf.score(Xva, yva)
    acc_test = clf.score(Xte, yte)  # held-out signers — the metric that counts
    print(f"train samples: {len(Xtr)} | input dim: {INPUT_DIM} | classes: {len(labels)}")
    print(f"val acc (held-out signers):  {acc_val:.1%}")
    print(f"TEST acc (held-out signers): {acc_test:.1%}   [Phase 1 target >=85%]")

    # Per-sign mean feature -> lets the demo synthesize a plausible attempt for a sign.
    prototypes = {
        sid: np.concatenate([Xtr[ytr == idx[sid]].mean(axis=0)]).tolist()
        for sid in labels
        if (ytr == idx[sid]).any()
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    clf.to_onnx(ARTIFACTS / "model.onnx")
    clf.save_labels(ARTIFACTS / "labels.json")
    (ARTIFACTS / "prototypes.json").write_text(json.dumps(prototypes))
    (ARTIFACTS / "metrics.json").write_text(
        json.dumps(
            {
                "model": "interim-linear",
                "synthetic": True,
                "input_dim": INPUT_DIM,
                "num_classes": len(labels),
                "val_accuracy": round(acc_val, 4),
                "test_accuracy_heldout_signers": round(acc_test, 4),
                "note": "Synthetic data. Replace with collected NSL signs before trusting.",
            },
            indent=2,
        )
    )

    for dest in (WEB_MODEL_DIR, API_MODEL_DIR):
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("model.onnx", "labels.json", "prototypes.json", "metrics.json"):
            shutil.copy(ARTIFACTS / name, dest / name)
    print(f"exported -> {ARTIFACTS}  (copied to web/ and api/ model dirs)")


if __name__ == "__main__":
    main()

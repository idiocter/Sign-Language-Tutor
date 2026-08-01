"""Train the INTERIM Devanagari fingerspelling classifier and export to ONNX (Phase 1.5).

Single-frame hand-landmark classification (21x3 = 63 features) over the Devanagari manual
alphabet. Runs on numpy + onnx (no torch), like the sign-recognition interim model.

    python scripts/train_fingerspelling.py

Reports top-1 accuracy on held-out signers (target ≥90%). Synthetic hand poses — measures
the pipeline, not real fingerspelling. Collect real handshapes with signers before trusting.

Artifacts -> ml/artifacts/fingerspelling/ and copied to the web/ and api/ model dirs.
"""

from __future__ import annotations

import json
import shutil

import numpy as np

from signbridge.config import ML_ROOT
from signbridge.fingerspelling import CHARS, HAND_FEATURE_DIM, ROMANS
from signbridge.models.linear_model import LinearSignClassifier

ARTIFACTS = ML_ROOT / "artifacts" / "fingerspelling"
WEB_DIR = ML_ROOT.parent / "web" / "public" / "models" / "fingerspelling"
API_DIR = ML_ROOT.parent / "api" / "models" / "fingerspelling"

N_SIGNERS = 8
SAMPLES_PER = 12


def _synth():
    """Return (X, y, signer_ids, prototypes) of synthetic single-frame hand features."""
    n_chars = len(CHARS)
    rng = np.random.default_rng(7)
    proto = rng.normal(0.0, 0.5, size=(n_chars, HAND_FEATURE_DIM)).astype(np.float32)
    signer_off = rng.normal(0.0, 0.12, size=(N_SIGNERS, HAND_FEATURE_DIM)).astype(np.float32)
    signer_gain = rng.normal(1.0, 0.15, size=(N_SIGNERS, HAND_FEATURE_DIM)).astype(np.float32)

    X, y, signers = [], [], []
    for ci in range(n_chars):
        for si in range(N_SIGNERS):
            for _ in range(SAMPLES_PER):
                v = proto[ci] * signer_gain[si] + signer_off[si]
                v = v + rng.normal(0.0, 0.06, size=HAND_FEATURE_DIM).astype(np.float32)
                X.append(v)
                y.append(ci)
                signers.append(si)
    return np.stack(X), np.array(y), np.array(signers), proto


def main() -> None:
    X, y, signers, proto = _synth()

    # Signer-independent split: hold out 1 signer for val, 1 for test.
    test_s, val_s = {N_SIGNERS - 1}, {N_SIGNERS - 2}
    is_test = np.isin(signers, list(test_s))
    is_val = np.isin(signers, list(val_s))
    is_train = ~(is_test | is_val)

    clf = LinearSignClassifier(CHARS, input_dim=HAND_FEATURE_DIM).fit(
        X[is_train], y[is_train], epochs=400, lr=0.5
    )
    acc_val = clf.score(X[is_val], y[is_val])
    acc_test = clf.score(X[is_test], y[is_test])
    print(f"chars: {len(CHARS)} | train: {is_train.sum()} | dim: {HAND_FEATURE_DIM}")
    print(f"val acc (held-out signer):  {acc_val:.1%}")
    print(f"TEST acc (held-out signer): {acc_test:.1%}   [Phase 1.5 target >=90%]")

    prototypes = {CHARS[ci]: proto[ci].tolist() for ci in range(len(CHARS))}

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    clf.to_onnx(ARTIFACTS / "model.onnx")
    (ARTIFACTS / "labels.json").write_text(
        json.dumps({"labels": CHARS, "romans": ROMANS}, ensure_ascii=False, indent=2)
    )
    (ARTIFACTS / "prototypes.json").write_text(json.dumps(prototypes))
    (ARTIFACTS / "metrics.json").write_text(
        json.dumps(
            {
                "model": "interim-linear-fingerspelling",
                "synthetic": True,
                "input_dim": HAND_FEATURE_DIM,
                "num_classes": len(CHARS),
                "val_accuracy": round(acc_val, 4),
                "test_accuracy_heldout_signers": round(acc_test, 4),
                "note": "Synthetic hand poses. Replace with collected handshapes before trusting.",
            },
            indent=2,
        )
    )
    for dest in (WEB_DIR, API_DIR):
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("model.onnx", "labels.json", "prototypes.json", "metrics.json"):
            shutil.copy(ARTIFACTS / name, dest / name)
    print(f"exported -> {ARTIFACTS} (copied to web/ and api/)")


if __name__ == "__main__":
    main()

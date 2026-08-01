"""Signer-independent evaluation (Phase 5).

Evaluates the exported recognition model on the **held-out test signers** — the split that
was never trained on (split_by_signer). Reports top-1 / top-3 accuracy, per-signer accuracy,
and the most-confused pairs, and writes ml/artifacts/eval_report.json.

    python scripts/eval.py

PROJECT_PLAN.md Phase 5: the signer-independent test set is the metric that actually
matters. On synthetic data this validates the harness; on real collected signs it is the
number you report.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

import numpy as np
import onnxruntime as ort

from signbridge.config import ML_ROOT
from signbridge.models.linear_model import pool_features
from signbridge.preprocessing import discover, split_by_signer

ARTIFACTS = ML_ROOT / "artifacts"


def _load_model():
    sess = ort.InferenceSession(str(ARTIFACTS / "model.onnx"))
    labels = json.loads((ARTIFACTS / "labels.json").read_text())["labels"]
    return sess, sess.get_inputs()[0].name, labels


def main() -> None:
    if not (ARTIFACTS / "model.onnx").exists():
        raise SystemExit("No model. Run scripts/train_lite.py first.")
    samples = discover()
    if not samples:
        raise SystemExit("No data in data/raw. Run scripts/synth_data.py first.")

    split = split_by_signer(samples, seed=1)
    test = split.test
    test_signers = sorted({s.signer_id for s in test})
    sess, input_name, labels = _load_model()
    label_idx = {l: i for i, l in enumerate(labels)}

    top1 = top3 = 0
    per_signer = defaultdict(lambda: [0, 0])  # signer -> [correct, total]
    confusion = Counter()

    for s in test:
        feats = pool_features(np.load(s.path))[None, :].astype(np.float32)
        probs = sess.run(None, {input_name: feats})[0][0]
        order = np.argsort(probs)[::-1]
        pred = labels[order[0]]
        truth = s.sign_id
        ok = pred == truth
        top1 += int(ok)
        top3 += int(truth in {labels[i] for i in order[:3]})
        per_signer[s.signer_id][0] += int(ok)
        per_signer[s.signer_id][1] += 1
        if not ok:
            confusion[(truth, pred)] += 1

    n = len(test)
    report = {
        "model": "interim-linear",
        "synthetic": True,
        "test_signers": test_signers,
        "n_test_samples": n,
        "top1_accuracy": round(top1 / n, 4),
        "top3_accuracy": round(top3 / n, 4),
        "per_signer_accuracy": {
            sg: round(c / t, 4) for sg, (c, t) in per_signer.items()
        },
        "top_confusions": [
            {"truth": a, "predicted": b, "count": c}
            for (a, b), c in confusion.most_common(10)
        ],
        "note": "Held-out signers (never trained on). Synthetic data measures the harness.",
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "eval_report.json").write_text(json.dumps(report, indent=2))

    print(f"held-out signers: {test_signers} | test samples: {n}")
    print(f"top-1: {report['top1_accuracy']:.1%} | top-3: {report['top3_accuracy']:.1%}")
    print(f"wrote {ARTIFACTS / 'eval_report.json'}")


if __name__ == "__main__":
    main()

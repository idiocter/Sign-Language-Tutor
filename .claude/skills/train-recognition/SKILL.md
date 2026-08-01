---
name: train-recognition
description: Regenerate data, train the recognition model, export ONNX, and verify it. Use when asked to (re)train recognition, refresh the model, or after changing the vocabulary/feature layout.
---

# Train the recognition model

Two models exist. Pick based on what data you have.

## Interim model (synthetic data, runs on any Python 3.11+ incl. 3.14)

Use for demos and pipeline changes. Trains in seconds, exports ONNX, updates the browser +
backend model dirs.

```bash
cd ml
./.venv/bin/python scripts/synth_data.py --signs 60 --signers 8 --takes 12 --clean
./.venv/bin/python scripts/train_lite.py          # reports held-out-signer accuracy
```

Verify end-to-end (backend must be running):
```bash
curl -s localhost:8000/inference/status
curl -s -X POST "localhost:8000/inference/demo?sign_id=NSL_0001"
```

Always state in your summary that this is **synthetic data** — the accuracy measures the
pipeline, not real NSL recognition.

## Production model (real NSL data, needs Python 3.11/3.12 + GPU)

Only when real collected takes exist under `ml/data/raw/`:
```bash
cd ml
./.venv/bin/python scripts/train.py --epochs 60 --batch-size 64
```

## Invariants to preserve

- Evaluation is on **held-out signers** (`split_by_signer`), never held-out clips.
- If you change the feature layout, change `ml/signbridge/config.py` AND
  `web/src/lib/landmarks.ts` together — they must match or inference breaks.
- Model artifacts are gitignored; they are build outputs, not source.

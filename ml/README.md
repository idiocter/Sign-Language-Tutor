# SignBridge — `ml/`

Data capture, preprocessing, recognition models, movement scoring, and tutor logic.

## Install

Two install profiles. The **foundation** profile is pure-Python + numpy and runs anywhere
(including Python 3.14). The **full** profile adds MediaPipe/PyTorch and currently needs
**Python 3.11 or 3.12**.

```bash
# Foundation: schema, vocabulary, transliteration, scoring, scheduler, tests
python -m venv .venv && source .venv/bin/activate
pip install -e ".[foundation]"
pytest

# Full ML/vision stack (capture + training) — use Python 3.11/3.12
pip install -e ".[full]"
```

## Layout

```
signbridge/
  config.py            Landmark feature layout — single source of truth
  schema.py            Typed sign dictionary (pydantic mirror of sign_schema.json)
  vocabulary.py        Load vocabulary.csv -> validated Signs
  transliterate.py     Roman -> Devanagari (Phase 0 deliverable, >=90% on test set)
  capture_tool.py      Webcam -> normalized landmark .npy   [full extra]
  preprocessing.py     normalize / augment / split_by_signer (signer-independent!)
  models/
    sign_transformer.py  Isolated-sign Transformer encoder + ONNX export  [full extra]
    fingerspelling.py    Devanagari manual-alphabet MobileNetV3 (Phase 1.5)  [full extra]
  scoring/dtw.py       DTW on joint angles, decomposed by sign parameter
  tutor/
    scheduler.py       FSRS spaced-repetition wrapper (+ offline fallback)
    calendar_bs.py     Bikram Sambat — presentation layer only
  agents/              Symbolic agents: Curriculum, Critique (language-aware)
data/
  sign_schema.json     JSON-Schema contract (from Guide/)
  vocabulary.csv       Editable core vocabulary (seed of the 200-sign set)
  sign_dictionary.json Generated: `python scripts/build_dictionary.py`
scripts/build_dictionary.py
tests/
```

## Key commands

```bash
python scripts/build_dictionary.py                        # compile the dictionary
python -m signbridge.capture_tool --signer S01 --sign NSL_0001   # collect data [full]
pytest -q                                                 # foundation tests
```

## The rules that are enforced in code, not just docs

- **Signer split, never clip split.** `preprocessing.split_by_signer` guarantees no signer
  appears in two splits and refuses to run with fewer than 3 signers.
- **Language-neutral IDs.** `schema.Sign` rejects any `sign_id` not matching `NSL_dddd`.
- **One feature layout.** Capture, preprocessing, and the model all import `config.py`, so
  their feature dimensions cannot drift apart.

## What still needs external work

- NSL landmark **data** (collect with signers — the real Phase 0–1 work)
- Trained **weights** for `SignTransformer` / `FingerspellingNet`
- WLASL pretraining (see `Guide/files/DOWNLOADS.md`)

Every deliberate placeholder is greppable: `grep -rn "STUB" signbridge`.

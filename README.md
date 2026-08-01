# SignBridge

Bilingual (English + Nepali) **Nepali Sign Language (NSL)** tutor and interpreter with an
animated signing avatar.

This repository is the working implementation of the plan in [`Guide/files/`](Guide/files).
Read those documents first — they are the source of truth for scope and sequencing:

- [`PROJECT_PLAN.md`](Guide/files/PROJECT_PLAN.md) — phases, exit criteria, timeline
- [`TECH_STACK.md`](Guide/files/TECH_STACK.md) — layer-by-layer technology choices
- [`DOWNLOADS.md`](Guide/files/DOWNLOADS.md) — models, datasets, assets to fetch

> **Non-negotiable from the plan:** Deaf NSL signers are involved from Phase 0, splits are
> **by signer** (never by clip), and signs are keyed by language-neutral IDs (`NSL_0001`),
> never by English words.

---

## Repository layout

```
.
├── Guide/          Planning documents (source of truth — do not delete)
├── ml/             Python: data capture, preprocessing, models, scoring, tutor logic
├── api/            FastAPI backend: schema/tutor/inference services
└── web/            Next.js 15 frontend: avatar, webcam recognizer, tutor UI (en/ne)
```

Each package has its own `README.md` with detailed setup. The rest of this file is the
quick start.

---

## What is built vs. what needs data / hardware / people

This scaffold implements everything that can be produced by writing code. The rest of the
plan is deliberately left as clearly-marked stubs because it depends on resources this
repository cannot generate:

| Built now (runnable) | Left as stubs (needs external work) |
|---|---|
| Sign schema loader + validation | **Production** recognition weights (need real NSL data + GPU) |
| 200-slot vocabulary + seeded core signs | NSL landmark dataset (Phase 0–1 collection with signers) |
| Roman → Devanagari transliteration + tests | Avatar `.glb` clips (Blender authoring, Phase 2) |
| Landmark capture tool (from the guide) | Whisper NSL/Nepali ASR fine-tune (Phase 4) |
| Preprocessing: normalize / augment / signer-split | Nepali TTS voice |
| Transformer encoder + full training loop | |
| **Interim recognition model** (synthetic data → ONNX) | |
| **End-to-end inference**: in-browser + backend | |
| DTW joint-angle scoring + error decomposition | |
| FSRS spaced-repetition scheduler | |
| All six Layer-7 agents (symbolic-only) | |
| **Text → NSL gloss → animated avatar** (procedural) | Authored Blender/ARKit `.glb` clips |
| **Co-articulation blending + ARKit facial track** | |
| FastAPI backend (schema, tutor, inference, produce) | |
| Next.js UI: avatar, webcam, recognition + sign demo, i18n | |

The interim model trains on **synthetic** data so the whole Phase 1 loop runs today; its
accuracy measures the pipeline, not real NSL recognition. Replace it via the
`train-recognition` skill once real signs are collected.

Claude Code **skills** and **subagents** for this repo live in [`.claude/`](.claude/README.md)
(`/add-sign`, `/train-recognition`, `/run-dev`; `nsl-data-reviewer`,
`signbridge-invariant-guard`).

`grep -rn "STUB" .` lists every deliberate placeholder and what it is waiting on.

---

## Quick start

### 1. Python (`ml/` + `api/`)

> **Runtime:** MediaPipe and PyTorch do not yet ship wheels for Python 3.14. Use
> **Python 3.11 or 3.12** for the ML/vision code. The pure-Python foundation
> (transliteration, schema, vocabulary, scoring, scheduler) runs on any 3.11+.

```bash
cd ml
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[foundation]"      # lightweight, no torch/mediapipe
pytest                              # transliteration + schema + preprocessing tests
```

Full ML stack (capture, training):

```bash
pip install -e ".[full]"            # adds mediapipe, torch, transformers, onnx
python -m signbridge.capture_tool --signer S01 --sign NSL_0001
```

### 2. Backend API (`api/`)

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload       # http://127.0.0.1:8000/docs
```

### 3. Frontend (`web/`)

```bash
cd web
npm install
npm run dev                         # http://localhost:3000
```

Download the MediaPipe `.task` models into `web/public/models/mediapipe/` before the
webcam recognizer will run — see [`DOWNLOADS.md`](Guide/files/DOWNLOADS.md#1-mediapipe-task-models).

---

## Phase status

Tracks [`PROJECT_PLAN.md`](Guide/files/PROJECT_PLAN.md). Checked = scaffolded and runnable.

- [x] **Phase 0 — Foundation:** schema, vocabulary, capture tool, transliteration, repo
- [~] **Phase 1 — Recognition MVP:** full pipeline runs end-to-end (synth data → train → ONNX → in-browser + backend inference, live demo); production model needs real NSL data + GPU
- [~] **Phase 1.5 — Fingerspelling:** MobileNetV3 classifier stub
- [~] **Phase 2 — Avatar:** text → gloss → animated signing runs end-to-end (procedural pose + ARKit facial track + co-articulation blending, live `/produce` + Sign-it page); needs authored `.glb` clips + deaf-advisor intelligibility validation. See [docs/avatar-authoring.md](docs/avatar-authoring.md)
- [~] **Phase 3 — Tutor loop:** FSRS scheduler + DTW scoring + all six Layer-7 agents built
- [ ] **Phase 4 — Interpreter mode:** contracts only
- [ ] **Phase 5 — Evaluation & deploy**

`[x]` done · `[~]` scaffolded, needs external work · `[ ]` contract/stub only

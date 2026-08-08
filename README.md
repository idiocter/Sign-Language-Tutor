# SignBridge

[![CI](https://github.com/idiocter/Sign-Language-Tutor/actions/workflows/ci.yml/badge.svg)](https://github.com/idiocter/Sign-Language-Tutor/actions/workflows/ci.yml)

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
| **Recursive remediation** (drill ladders from a failed sign) | |
| **Learner-data flywheel** (gated, human-approved retraining pool) | Reviewer sign-off on real learner takes |
| All six Layer-7 agents (symbolic-only) | |
| **Text → NSL gloss → animated avatar** (procedural) | Authored Blender/ARKit `.glb` clips |
| **Personal avatar** (drop-in Ready Player Me `.glb`) | Photoreal photo→3D likeness (external generator) |
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

## Recursive learning

Two loops that feed themselves. Both are symbolic-only and keep the plan's invariants.

### 1. Recursive curriculum descent — when a learner fails a sign

A failure is not a cue for "try again" or for more new signs. `RemediationAgent`
(`ml/signbridge/agents/remediation.py`) takes the sign and the parameter DTW says cost the
most, then walks *down* the sign's prerequisites and phonological neighbours — signs
sharing that handshape / location / movement / orientation — until it reaches something
the learner has already mastered. The drills come back **foundation-first**, so the learner
rebuilds from the bottom and re-ascends to the sign they missed:

```
d3 component  Put your hands at chest_center and hold.       ← isolate the component, once
d3 sign       Now build up: sign "I". It shares the location you missed.
d2 sign       Now build up: sign "please".
d1 sign       Now build up: sign "hello".
d0 target     Back to "sorry". Watch the location this time.  ← the sign that failed
```

Depth, plan length, and revisits are all capped, so a densely-connected dictionary can
never produce an endless lesson. `CurriculumAgent` folds the ladder into the lesson and
gives up new material to make room for it.

```bash
curl -s localhost:8000/tutor/remediation \
  -H 'content-type: application/json' \
  -d '{"sign_id":"NSL_0003","failed_parameter":"location","language":"ne"}'

# stateful: score an attempt, record it, get the ladder back if it failed
curl -s -X POST localhost:8000/tutor/learner/1/attempt -d @attempt.json
```

### 2. The data flywheel — the model improving on its own output

```
capture → score (DTW) + recognize (ONNX) → gate → candidate → human review
        → promote into data/raw/ → retrain → better model → …
```

Each turn is a **generation**, recorded in `ml/data/candidates/flywheel_state.json`, so a
regression can be traced to the generation that admitted the data. Three rules keep the
loop from eating itself (`ml/signbridge/flywheel.py`):

1. **Nothing enters training without a human.** The gate only produces *candidates*;
   `/flywheel/review` and `/flywheel/promote` need `SIGNBRIDGE_REVIEWER_TOKEN`, which is
   unset by default — so out of the box nothing can be approved at all.
2. **Learner data augments, never founds, a class.** A sign needs two distinct studio
   signers before any learner take is promoted for it. Otherwise the model would be
   learning a sign from its own predictions about that sign.
3. **No signer may dominate.** A per-signer share cap protects the signer-independent
   split — a flywheel fed mostly by one keen learner produces a model that works for
   exactly one person.

The gate also refuses takes the recognizer reads as a *different* sign (the label is
unreliable whoever is wrong), near-duplicates of a take the same learner already sent, and
anything `DataCuratorAgent` flags. Contributions require explicit `consent`; candidates are
gitignored personal data.

```bash
curl -s localhost:8000/flywheel/status           # generation, queue depth, retrain due?
curl -s localhost:8000/flywheel/queue            # what is waiting for a reviewer

python ml/scripts/promote_candidates.py --report # where the loop stands
python ml/scripts/promote_candidates.py          # dry run: what would move
python ml/scripts/promote_candidates.py --apply  # move it, bump the generation
python ml/scripts/train_lite.py                  # retrain — next turn of the loop
```

---

## Quick start

### 0. Everything at once (recommended)

First-time setup, then run the whole stack (FastAPI on `:8000` + Next.js on `:3000`) with one
command:

```bash
make setup          # create ml/.venv, api/.venv; install web/node_modules
make data train     # generate synthetic data + train the interim recognition model
./dev.sh            # or: make dev  — starts backend + frontend together (Ctrl-C stops both)
```

- Frontend: http://localhost:3000 (redirects to `/en`)
- API docs: http://127.0.0.1:8000/docs

Verify both are up:

```bash
curl -s -o /dev/null -w "api %{http_code}\n" localhost:8000/health
curl -s -o /dev/null -w "web %{http_code}\n" localhost:3000/en
```

The steps below set up each package individually if you'd rather run them separately.

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

All seven phases are implemented and run end-to-end. `[~]` marks phases whose plan exit
criteria still depend on external work (real NSL data, GPU training, authored `.glb` clips,
deaf-community validation, cloud accounts) — the pipeline is built and runnable now with
synthetic/interim/browser-native stand-ins, clearly labeled, with the seam to swap the real
asset in.

- [x] **Phase 0 — Foundation:** schema, vocabulary, capture tool, transliteration, repo
- [~] **Phase 1 — Recognition MVP:** synth data → signer-split train → ONNX → in-browser + backend inference, live demo; production model needs real NSL data + GPU
- [~] **Phase 1.5 — Fingerspelling:** 48-char Devanagari alphabet, interim classifier + ONNX, live spell demo; needs real handshape data
- [~] **Phase 2 — Avatar:** text → gloss → animated signing (procedural pose + ARKit facial track + co-articulation), live `/produce` + Sign-it page. Drop a rigged Ready Player Me `.glb` at `web/public/avatar/character.glb` to sign as a personal avatar (auto-loaded, no config); needs authored `.glb` clips + intelligibility validation. See [docs/avatar-authoring.md](docs/avatar-authoring.md)
- [~] **Phase 3 — Tutor loop:** end-to-end lessons (avatar → FSRS rating → scheduled review), streaks in Bikram Sambat, DTW scoring, all six Layer-7 agents, recursive remediation + the learner-data flywheel (see [Recursive learning](#recursive-learning))
- [~] **Phase 4 — Interpreter mode:** bidirectional — text/speech → sign, sign → text/speech (browser Web Speech; text fallback always); needs Nepali ASR/TTS + continuous recognition
- [~] **Phase 5 — Evaluation & deploy:** signer-independent eval harness, native-signer intelligibility rating collection, Docker + Fly/Vercel configs. See [docs/deploy.md](docs/deploy.md); actual cloud deploy + community ratings are external

`[x]` done · `[~]` built & runnable, real-world exit criteria need external work

## What genuinely remains (not code)

Collect NSL data with deaf signers · train the production models on a GPU · author avatar
`.glb` clips in Blender with ARKit blendshapes · fine-tune Nepali ASR/TTS · gather
native-signer intelligibility ratings · run the cloud deploy. The code, contracts, docs,
and swap-in seams for all of these exist.

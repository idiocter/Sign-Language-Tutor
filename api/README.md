# SignBridge — `api/`

FastAPI backend. Serves the sign dictionary, transliteration, the tutor loop (curriculum
+ FSRS scheduling + DTW scoring), and a WebSocket inference fallback. It builds on the
`signbridge` package in [`../ml`](../ml).

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate    # 3.11+ is fine for the API
pip install -e ../ml[foundation]     # provides the `signbridge` package
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000/docs
pytest                               # smoke tests
```

Defaults to SQLite (`./signbridge.db`) and in-memory scheduling, so it runs with **no
external services**. For production set `DATABASE_URL` (Postgres + pgvector) and add Redis.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/signs` `?category=` | list signs |
| GET | `/signs/{sign_id}` | one sign |
| POST | `/signs/transliterate` | Romanized Nepali → Devanagari |
| POST | `/tutor/lesson` | next lesson (Curriculum agent) |
| POST | `/tutor/review` | submit a rating → next due date (FSRS) |
| POST | `/tutor/score` | DTW score + localized Critique feedback |
| POST | `/tutor/remediation` | recursive drill ladder for a failed sign |
| POST | `/tutor/learner/{id}/attempt` | score + record an attempt, ladder back on failure |
| GET | `/flywheel/status` | generation, candidate queue, retrain due? |
| POST | `/flywheel/contribute` | donate a scored take as a training candidate (consent required) |
| GET | `/flywheel/queue` | candidates awaiting review |
| POST | `/flywheel/review/{id}` | approve/reject a candidate **(reviewer token)** |
| POST | `/flywheel/promote` | move approved takes into training **(reviewer token)** |
| WS | `/ws/inference` | streaming recognition **fallback** (stub) |

Interactive docs at `/docs` once running.

## Notes

- **Recognition runs in the browser** by default (video never leaves the device). The
  `/ws/inference` endpoint is only the fallback for clients without WebGPU, and currently
  returns a **stub** prediction until a model is trained.
- `/tutor/score` takes normalized landmark arrays `(frames, FEATURE_DIM)` for both the
  learner attempt and the reference sign, and returns the per-parameter error breakdown.
- **The flywheel is default-deny.** `/flywheel/review` and `/flywheel/promote` are the only
  endpoints that can change what the model trains on, and both 503 unless
  `SIGNBRIDGE_REVIEWER_TOKEN` is set; requests then need a matching `X-Reviewer-Token`
  header. Contributions still queue safely without it — they just wait for a reviewer.
- `/flywheel/contribute` requires explicit `consent` and refuses a take it cannot
  cross-check against the recognizer. See the [Recursive learning](../README.md#recursive-learning)
  section for the rules the gate and promoter enforce.

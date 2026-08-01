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
| WS | `/ws/inference` | streaming recognition **fallback** (stub) |

Interactive docs at `/docs` once running.

## Notes

- **Recognition runs in the browser** by default (video never leaves the device). The
  `/ws/inference` endpoint is only the fallback for clients without WebGPU, and currently
  returns a **stub** prediction until a model is trained.
- `/tutor/score` takes normalized landmark arrays `(frames, FEATURE_DIM)` for both the
  learner attempt and the reference sign, and returns the per-parameter error breakdown.

# Deploying SignBridge (Phase 5)

Target topology (PROJECT_PLAN.md Phase 5 / TECH_STACK.md Layer 4):

- **Frontend → Vercel** (Next.js)
- **Backend → Fly.io or Railway** (FastAPI)
- **Assets (avatar `.glb` clips, ONNX models) → Cloudflare R2**
- **Database → Postgres** (pgvector-ready), **Redis** for sessions/cache

## 0. Generate model artifacts first

The API serves the recognition/fingerspelling ONNX models from `api/models/`. They are
gitignored build outputs — generate them before building images:

```bash
make data train      # writes api/models/** and web/public/models/**
```

For production, publish these (and any authored `.glb` clips) to Cloudflare R2 and have the
API/web pull them at deploy time, rather than baking large binaries into images.

## 1. Local production-like run (Docker)

```bash
docker compose up --build
# web -> http://localhost:3000   api -> http://localhost:8000/docs
```

## 2. Backend → Fly.io

```bash
cd <repo root>
fly launch --no-deploy            # creates the app from api/fly.toml
fly secrets set \
  DATABASE_URL="postgresql+psycopg://USER:PASS@HOST/signbridge" \
  CORS_ORIGINS="https://<your-vercel-domain>"
fly deploy                        # builds api/Dockerfile
```

Railway alternative: point it at `api/Dockerfile` (root context) and set the same env vars.

## 3. Frontend → Vercel

- Import the repo; set **Root Directory = `web`**.
- Env var: `NEXT_PUBLIC_API_BASE=https://<your-fly-app>.fly.dev`
- Deploy. `web/vercel.json` pins the framework and commands.

> `NEXT_PUBLIC_*` is inlined at build time — set it before the build, and rebuild when the
> API URL changes.

## 4. Database

- Provision Postgres (Fly Postgres, Railway, Neon, or Supabase) and set `DATABASE_URL`.
- Tables are created on startup (`Base.metadata.create_all`). For real migrations, add
  Alembic before you have production data you can't drop.
- Enable `pgvector` when you add embedding search (Phase 4 dedupe / nearest-sign).

## 5. Environment variables

| Service | Variable | Purpose |
|---|---|---|
| API | `DATABASE_URL` | Postgres connection (defaults to SQLite) |
| API | `CORS_ORIGINS` | comma-separated allowed origins (the web domain) |
| web | `NEXT_PUBLIC_API_BASE` | API base URL (build-time) |
| web | `NEXT_PUBLIC_ORT_WASM` | onnxruntime-web wasm base (optional, for offline) |
| web | `NEXT_PUBLIC_MP_WASM` | MediaPipe wasm base (optional) |

## Pre-launch checklist (from the plan)

- [ ] Signer-independent test set evaluated (`python ml/scripts/eval.py`) — **never** trained on
- [ ] Avatar intelligibility rated ≥4/5 by native NSL signers (`/eval` page collects this)
- [ ] Usability tested with Nepali-dominant **and** English-comfortable deaf users
- [ ] No video leaves the device (recognition runs in-browser)
- [ ] Nepali text fallback works everywhere ASR/TTS is offered

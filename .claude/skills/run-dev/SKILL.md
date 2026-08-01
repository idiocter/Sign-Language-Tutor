---
name: run-dev
description: Start the SignBridge backend and frontend together and verify both are up. Use when asked to run, start, launch, or serve the app / the whole stack.
---

# Run the full stack

Starts FastAPI (port 8000) and Next.js (port 3000) together.

## First time only — setup

```bash
make setup        # creates ml/.venv, api/.venv, installs web/node_modules
make data train   # generate synthetic data + train the interim model (optional but
                  # needed for the recognition demo to work)
```

## Start both

```bash
./dev.sh          # or: make dev
```

- Frontend: http://localhost:3000 (redirects to /en)
- Backend docs: http://127.0.0.1:8000/docs

## Verify (run these; don't assume it worked)

```bash
curl -s -o /dev/null -w "api %{http_code}\n"  localhost:8000/health
curl -s -o /dev/null -w "web %{http_code}\n"  localhost:3000/en
curl -s localhost:8000/inference/status
```

The recognition demo is on the **Practice** page. If `/inference/status` shows
`ready: false`, run `make data train` first.

Ctrl-C stops both. The backend runs with `--reload` and the frontend hot-reloads, so edits
apply without restarting.

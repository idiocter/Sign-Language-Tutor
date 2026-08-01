#!/usr/bin/env bash
# Start the SignBridge backend (FastAPI) and frontend (Next.js) together.
#
#   ./dev.sh
#
# Backend -> http://127.0.0.1:8000  (docs at /docs)
# Frontend -> http://localhost:3000  (redirects to /en)
#
# Assumes setup is done (see README quick start):
#   ml/.venv  and  api/.venv  created and installed;  web/node_modules installed.
# Ctrl-C stops both.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

pids=()
cleanup() {
  echo ""
  echo "stopping…"
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# --- Backend ---
if [[ ! -x "$ROOT/api/.venv/bin/uvicorn" ]]; then
  echo "!! api/.venv not found. Run: cd api && python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ../ml[foundation] && pip install -r requirements.txt"
  exit 1
fi
echo ">> backend  http://127.0.0.1:$API_PORT  (docs at /docs)"
(cd "$ROOT/api" && exec .venv/bin/uvicorn app.main:app --port "$API_PORT" --reload) &
pids+=($!)

# --- Frontend ---
if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "!! web/node_modules not found. Run: cd web && npm install"
  exit 1
fi
echo ">> frontend http://localhost:$WEB_PORT"
(cd "$ROOT/web" && exec npm run dev -- --port "$WEB_PORT") &
pids+=($!)

echo ">> both running. Ctrl-C to stop."
wait

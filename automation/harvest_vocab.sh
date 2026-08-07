#!/usr/bin/env bash
# Idiomatic automation: harvest candidate vocabulary into a staging CSV. Point cron or CI at
# this; it's what the n8n workflow shells out to. Never touches vocabulary.csv directly — a
# human + nsl-data-reviewer complete and approve staged rows before training.
#
# Usage:  NSL_SOURCE_URL=https://example.org/nsl ./automation/harvest_vocab.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${NSL_SOURCE_URL:?set NSL_SOURCE_URL to a source you are permitted to scrape}"
PY="${PYTHON:-$ROOT/ml/.venv/bin/python}"
OUT="$ROOT/tools/scrape_vocabulary/staging_vocab.csv"

"$PY" "$ROOT/tools/scrape_vocabulary/scrape.py" --url "$NSL_SOURCE_URL" --check-robots --out "$OUT"

rows=$(($(wc -l < "$OUT") - 1))
echo "staged $rows candidate rows -> $OUT"
echo "next: review + complete phonology, then merge approved rows into ml/data/vocabulary.csv"

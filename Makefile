# SignBridge convenience targets. See README.md for details.
# Note: the ML/vision `full` extra (capture, torch training) needs Python 3.11/3.12.

.PHONY: help setup-ml setup-api setup-web setup data train eval test dev models

help:
	@echo "make setup     - create venvs + install ml, api, web"
	@echo "make data      - generate synthetic NSL landmark data (Phase 1)"
	@echo "make train     - train the interim recognition model + export ONNX"
	@echo "make test      - run ml + api test suites"
	@echo "make dev       - start backend + frontend together"

setup-ml:
	cd ml && python3 -m venv .venv && ./.venv/bin/pip install -e ".[foundation]"

setup-api:
	cd api && python3 -m venv .venv && ./.venv/bin/pip install -e "../ml[foundation]" && ./.venv/bin/pip install -r requirements.txt

setup-web:
	cd web && npm install

setup: setup-ml setup-api setup-web

data:
	cd ml && ./.venv/bin/python scripts/synth_data.py --signs 60 --signers 8 --takes 12 --clean

train:
	cd ml && ./.venv/bin/python scripts/train_lite.py
	cd ml && ./.venv/bin/python scripts/train_fingerspelling.py

eval:
	cd ml && ./.venv/bin/python scripts/eval.py

models:
	bash scripts/download-models.sh

test:
	cd ml && ./.venv/bin/pytest -q
	cd api && ./.venv/bin/pytest -q

dev:
	./dev.sh

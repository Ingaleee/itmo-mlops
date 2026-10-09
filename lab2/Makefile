.PHONY: venv index test quality negative build up down smoke local-check

PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

venv:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -r requirements-dev.txt

index: venv
	$(BIN)/python scripts/build_index.py --output artifacts

test: index
	$(BIN)/python -m pytest -q

quality: index
	$(BIN)/python scripts/evaluate.py --artifact-dir artifacts

negative: index
	$(BIN)/python scripts/check_quality.py

build:
	docker compose build search

up:
	docker compose up -d --build search

down:
	docker compose down

smoke:
	$(PYTHON) scripts/smoke_local.py

local-check: test quality negative build

.PHONY: setup test lint fmt run report clean

VENV := .venv
PY   := $(VENV)/bin/python

setup:
	uv venv $(VENV)
	uv pip install --python $(PY) -e ".[dev,report]"
	@echo "Live data is optional: uv pip install --python $(PY) -e '.[data]'"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests scripts
	$(PY) -m ruff format --check src tests scripts

fmt:
	$(PY) -m ruff format src tests scripts
	$(PY) -m ruff check --fix src tests scripts

run:
	$(PY) scripts/run_pipeline.py --config configs/strategies/momentum_rf.yaml

report:
	$(PY) scripts/build_analysis_pdf.py

clean:
	rm -rf .pytest_cache .ruff_cache reports/*.png reports/*.csv
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

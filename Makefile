.PHONY: install format lint test run worker docker-up docker-down

VENV?=.venv
PYTHON?=python3
PIP?=$(VENV)/bin/pip
UVICORN?=$(VENV)/bin/uvicorn

install: $(VENV)/bin/activate

$(VENV)/bin/activate: pyproject.toml
$(PYTHON) -m venv $(VENV)
$(PIP) install --upgrade pip
$(PIP) install -e .[test]
touch $(VENV)/bin/activate

format:
$(VENV)/bin/isort app
$(VENV)/bin/black app

lint:
$(VENV)/bin/black --check app
$(VENV)/bin/isort --check-only app

test:
$(VENV)/bin/pytest

run:
$(UVICORN) app.main:app --reload

worker:
$(VENV)/bin/python -m app.workers.ingestion

docker-up:
docker compose up --build

docker-down:
docker compose down -v

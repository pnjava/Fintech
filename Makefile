PYTHON ?= python3
PIP ?= pip
APP_MODULE ?= api.app.main:app
ENV_FILE ?= .env

.PHONY: setup lint typecheck test cov run migrate docker-up docker-down format

setup:
    $(PIP) install --upgrade pip
    $(PIP) install -e .[dev]
    pre-commit install

format:
    black api
    isort api

lint:
    ruff check api

typecheck:
    mypy api

test:
    pytest

cov:
    pytest --cov=api --cov-report=xml --cov-report=term-missing

run:
    uvicorn $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload --env-file $(ENV_FILE)

migrate:
    alembic upgrade head

docker-up:
    docker compose up -d --build

docker-down:
    docker compose down --remove-orphans

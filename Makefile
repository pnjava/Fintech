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

# --- ML / GPU helpers ---
.PHONY: train-pt train-xgb profile-pt bento-serve bento-build grpc-serve grpc-client kserve-apply

train-pt:
	python ml/train_pytorch.py

train-xgb:
	python -m ml.train_xgboost

profile-pt:
	python -m ml.profiler_torch

bento-serve:
	bentoml serve serving/bento/service.py:svc --port 9000 --host 0.0.0.0

bento-build:
	bentoml build serving/bento

grpc-serve:
	$(PYTHON) scripts/gen_proto.ps1 || true
	$(PYTHON) -m ml_grpc.server

kserve-apply:
	kubectl apply -f infra/k8s/kserve/inferenceservice.yaml

grpc-client:
	$(PYTHON) -m ml_grpc.client

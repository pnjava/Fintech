# Fintech Platform — API, GPU ML, and Observability

Production-focused Fintech backend with FastAPI services, async workers, and a GPU ML pipeline. Includes containerization, CI/CD, observability (Prometheus/Grafana/OTel), and model serving via BentoML, gRPC, and KServe on EKS.

Highlights
- Python/C++ ready: Python 3.11 app stack; GPU containers based on CUDA runtime.
- GPU training/inference: RAPIDS/cuDF preprocessing, PyTorch training, TensorRT attempt, XGBoost-GPU (with CPU fallbacks).
- Serving & scale: BentoML service, gRPC API, KServe manifest for autoscaling on EKS.
- Profiling & tuning: PyTorch profiler; Nsight Systems/Compute ready in GPU containers.
- Observability: Prometheus metrics, OpenTelemetry tracing; Grafana dashboards.

Repository Layout
- `app/` FastAPI app, services, schemas, and observability.
- `workers/` Async workers for ingestion/reporting/data retention.
- `ml/` GPU ML pipeline: training, inference, profiling utilities.
- `ml_grpc/` gRPC proto, generated stubs (via scripts), and server.
- `serving/bento/` BentoML service and `bentofile.yaml`.
- `infra/helm/fintech/` Helm chart; `infra/k8s/kserve/` KServe manifest.
- `ops/` Prometheus, OpenTelemetry, and ELK configs.
- `docker-compose.yml` Local stack; `Dockerfile` app; `Dockerfile.gpu` GPU image.

Prerequisites
- Python 3.11, Docker, and Docker Compose
- Optional GPU: NVIDIA driver and NVIDIA Container Toolkit
- Optional RAPIDS/TensorRT: matching CUDA version

Quickstart
- Install dev dependencies: `pip install -e .[dev]`
- Local stack: `make docker-up` then open API at `http://localhost:8000`
- Tests and checks: `make test` `make lint` `make typecheck` `make cov`
- Tear down: `make docker-down`

CI/CD
- App CI: `.github/workflows/ci.yml`
- GPU image build: `.github/workflows/gpu-ci.yml` (builds `Dockerfile.gpu`)

Observability
- Metrics: `/metrics` exposed by API and workers
- OpenTelemetry: OTLP exporter configured; collector at `ops/otel/collector-config.yaml`
- Prometheus/Grafana: services in `docker-compose.yml`
- Runbooks: `docs/runbooks/observability.md`, `docs/runbooks/gpu-inference.md`

GPU ML Pipeline
- PyTorch training: `python ml/train_pytorch.py` → writes `ml/artifacts/tinynet.ts`
- XGBoost-GPU: `python ml/train_xgboost.py` (auto-fallback to CPU)
- RAPIDS/cuDF preprocess: `python ml/preprocess_cudf.py --input data.csv --output data.parquet`
- TensorRT attempt: `python ml/infer_tensorrt.py --ts ml/artifacts/tinynet.ts`
- Profiling: `python ml/profiler_torch.py` → traces in `artifacts/traces`

Serving Options
- BentoML (local):
  - `make bento-serve` or `docker compose up inference-gpu`
  - Service: `serving/bento/service.py`
  - Config: `serving/bento/bentofile.yaml`
- gRPC:
  - Generate stubs: `scripts/gen_proto.ps1` (PowerShell) or `scripts/gen_proto.sh`
  - Start server: `make grpc-serve` (module `ml_grpc.server`)
  - Proto: `ml_grpc/model.proto`, stubs in `ml_grpc/generated/`
- KServe on EKS:
  - Build/push an image (e.g., Bento build), set `image:` in `infra/k8s/kserve/inferenceservice.yaml`
  - Apply: `make kserve-apply`

Containers
- App: `Dockerfile` (CPU) used by API/worker services
- GPU: `Dockerfile.gpu` (CUDA 12.2 + Python 3.11) for training/serving
- Compose includes Postgres, Localstack, Kafka, OTel Collector, Prometheus, Grafana, ELK, API, workers, and `inference-gpu`

Make Targets
- `make train-pt` Train PyTorch model and export TorchScript
- `make train-xgb` Train XGBoost model (GPU/CPU)
- `make profile-pt` Run PyTorch profiler and export traces
- `make bento-serve` Start Bento service on `:9000`
- `make bento-build` Build Bento image
- `make grpc-serve` Generate gRPC stubs and serve
- `make kserve-apply` Apply KServe InferenceService

EKS & Autoscaling
- Deploy app with `infra/helm/fintech` and enable Prometheus scraping
- Use a node group with GPU instance types and cluster-autoscaler
- For GPU metrics, deploy NVIDIA DCGM Exporter; add a Prometheus scrape; import a GPU Grafana dashboard

Performance & Profiling
- PyTorch profiler traces in `artifacts/traces` (use TensorBoard)
- Nsight Systems/Compute can run in the GPU container for kernel analysis
- Optimize with mixed precision, TorchScript, TensorRT where applicable

Security & Compliance
- JWT-based auth, RBAC, audit logs (see `app/obs/` and API routes)
- Data retention worker and runbook in `docs/runbooks/data-retention.md`

Notes
- ML scripts auto-detect CUDA and fall back to CPU when not available
- On Windows, prefer `scripts/gen_proto.ps1`; on Bash, use `scripts/gen_proto.sh`


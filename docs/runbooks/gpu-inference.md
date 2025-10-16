GPU training, optimization, and serving runbook

Training
- PyTorch: `python ml/train_pytorch.py` → writes `ml/artifacts/tinynet.ts`.
- XGBoost (GPU): `python ml/train_xgboost.py` (falls back to CPU).
- RAPIDS cuDF preprocessing: `python ml/preprocess_cudf.py --input data.csv --output data.parquet`.

Profiling
- PyTorch Profiler: `python ml/profiler_torch.py` → open in TensorBoard at `artifacts/traces`.
- Nsight Systems/Compute: run container with `--gpus all` and use `nsys`/`ncu` in PATH; export reports and attach to Grafana if desired.

Serving
- BentoML local: `make bento-serve` or `docker compose up inference-gpu`.
- gRPC: generate stubs with `scripts/gen_proto.ps1` then `python -m grpc.server`.
- KServe: build/push image from Bento (`bentoml build`), set `image:` in `infra/k8s/kserve/inferenceservice.yaml`, then `make kserve-apply`.

Observability
- Prometheus metrics exposed via existing `/metrics` and Bento default metrics.
- For GPU metrics on EKS, deploy `nvidia/dcgm-exporter` and add Prometheus scrape config; import a GPU dashboard in Grafana.

Scaling on EKS
- Use node group with GPU instances, cluster-autoscaler, and KServe autoscaling via HPA.


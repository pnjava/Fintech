# Observability Runbook

## Metrics
- Prometheus endpoint exposed at `https://<host>/metrics` via `PrometheusMiddleware`.
- Key metrics:
  - `http_request_latency_seconds` (histogram) for API latency percentiles.
  - `http_requests_total` and `http_request_errors_total` for rate/error monitoring.
  - `worker_queue_depth{queue_name=...}` for SQS/Kafka backlog visibility.
  - `data_retention_*` counters for nightly purge totals.

## Tracing
- Tracing initialised via `initialise_tracing` with OTLP exporter targeting `OTEL_EXPORTER_ENDPOINT`.
- FastAPI, SQLAlchemy, and worker spans propagate `traceparent` headers end-to-end.
- Workers use `worker_span` to link queue messages back to originating API calls.

## Dashboards & Alerts
- Import `docs/dashboards/observability-dashboard.json` into Grafana.
- Recommended alerts:
  - P95 latency > 2s for 5 minutes.
  - Error rate > 5% for 5 minutes.
  - Queue depth > threshold for >10 minutes.

## Troubleshooting Steps
1. **Check Metrics** – query Prometheus for `sum(rate(http_request_errors_total[5m]))`.
2. **Inspect Traces** – search for the `trace_id` from the `X-Request-ID` header in the tracing backend.
3. **Review Logs** – structured audit logs stored in S3 bucket `AUDIT_LOG_BUCKET` with prefix `AUDIT_LOG_PREFIX`.
4. **Validate Instrumentation** – run unit tests `tests/unit/test_observability.py` to ensure instrumentation is functioning.

## Useful Commands
```bash
uvicorn app.main:app --reload --port 8000
pytest --cov=app --cov-report=term-missing
python scripts/generate_openapi.py
python -m workers.upload_validator.main
python -m workers.transaction_reporting.main
```

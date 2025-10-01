# ADR 0001: Observability Stack Standardisation

## Status
Accepted

## Context
The platform must provide latency, rate, error, and backlog visibility across API and worker processes while satisfying compliance audit requirements. The codebase previously lacked consistent metrics and trace propagation.

## Decision
- Adopt Prometheus metrics via `PrometheusMiddleware` for API request instrumentation and worker queue depth gauges.
- Use OpenTelemetry SDK with OTLP exporter for traces. FastAPI, SQLAlchemy, and workers are instrumented to propagate `traceparent` headers.
- Emit data retention counters to track compliance deletes and expose `/metrics` for scraping.
- Provide Grafana dashboards and runbooks checked into `docs/` for reproducible operations.

## Consequences
- Services require the OTLP collector endpoint to be configured in production environments.
- Workers must import `app.workers.observability` to report queue depth and tracing context.
- Prometheus client registry is shared across API and worker processes; processes must run with unique metric namespaces when using multiprocess setups.

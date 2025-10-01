from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace

from app.obs import (
    QUEUE_DEPTH_GAUGE,
    PrometheusMiddleware,
    initialise_tracing,
    inject_traceparent,
    metrics_router,
    report_queue_depth,
    span_from_traceparent,
)


def test_metrics_endpoint_exposes_counters() -> None:
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)
    app.include_router(metrics_router)

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_report_queue_depth_updates_gauge() -> None:
    report_queue_depth("test-queue", 7)
    sample_family = next(iter(QUEUE_DEPTH_GAUGE.collect()))
    sample = next(
        item for item in sample_family.samples if item.labels["queue_name"] == "test-queue"
    )
    assert sample.value == 7


def test_span_from_traceparent_links_context() -> None:
    initialise_tracing(service_name="unit-test-service")
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("parent"):
        carrier = inject_traceparent({})
    traceparent = carrier.get("traceparent")
    assert traceparent is not None

    with span_from_traceparent("child", traceparent) as span:
        assert (
            span.get_span_context().trace_id == trace.get_current_span().get_span_context().trace_id
        )

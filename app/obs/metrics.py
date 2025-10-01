"""Prometheus metrics utilities for API and worker processes."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_LATENCY_SECONDS = Histogram(
    "http_request_latency_seconds",
    "Latency of HTTP requests in seconds.",
    labelnames=("method", "path"),
)
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed.",
    labelnames=("method", "path", "status"),
)
REQUEST_ERROR_COUNTER = Counter(
    "http_request_errors_total",
    "Total number of HTTP requests that resulted in server errors.",
    labelnames=("method", "path", "status"),
)
QUEUE_DEPTH_GAUGE = Gauge(
    "worker_queue_depth",
    "Depth of asynchronous worker queues awaiting processing.",
    labelnames=("queue_name",),
)
DATA_RETENTION_AUDIT_COUNTER = Counter(
    "data_retention_audit_logs_deleted_total",
    "Count of audit log records deleted by the retention job.",
)
DATA_RETENTION_TRANSACTION_COUNTER = Counter(
    "data_retention_transactions_deleted_total",
    "Count of transaction records deleted by the retention job.",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records request metrics for Prometheus scraping."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # type: ignore[override]
        method = request.method
        path = request.url.path
        start_time = time.perf_counter()
        status = "500"

        try:
            response = await call_next(request)
            status = str(response.status_code)
            if response.status_code >= 500:
                REQUEST_ERROR_COUNTER.labels(method=method, path=path, status=status).inc()
            return response
        except Exception:
            REQUEST_ERROR_COUNTER.labels(method=method, path=path, status="500").inc()
            raise
        finally:
            latency = time.perf_counter() - start_time
            REQUEST_LATENCY_SECONDS.labels(method=method, path=path).observe(latency)
            REQUEST_COUNTER.labels(method=method, path=path, status=status).inc()


metrics_router = APIRouter(tags=["observability"])


@metrics_router.get("/metrics", include_in_schema=False)
def metrics_endpoint() -> Response:
    """Expose Prometheus metrics for scraping."""
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


def report_queue_depth(queue_name: str, depth: int | float) -> None:
    """Report the depth of a named worker queue."""
    QUEUE_DEPTH_GAUGE.labels(queue_name=queue_name).set(max(0.0, float(depth)))


__all__ = [
    "PrometheusMiddleware",
    "DATA_RETENTION_AUDIT_COUNTER",
    "DATA_RETENTION_TRANSACTION_COUNTER",
    "QUEUE_DEPTH_GAUGE",
    "REQUEST_COUNTER",
    "REQUEST_ERROR_COUNTER",
    "REQUEST_LATENCY_SECONDS",
    "metrics_endpoint",
    "metrics_router",
    "report_queue_depth",
]

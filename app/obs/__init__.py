"""Observability utilities."""

from .audit import AuditLogRecord, AuditMiddleware
from .metrics import (
    DATA_RETENTION_AUDIT_COUNTER,
    DATA_RETENTION_TRANSACTION_COUNTER,
    QUEUE_DEPTH_GAUGE,
    REQUEST_COUNTER,
    REQUEST_ERROR_COUNTER,
    REQUEST_LATENCY_SECONDS,
    PrometheusMiddleware,
    metrics_router,
    report_queue_depth,
)
from .tracing import (
    initialise_tracing,
    inject_traceparent,
    instrument_fastapi_app,
    instrument_sqlalchemy_engine,
    span_from_traceparent,
)

__all__ = [
    "AuditLogRecord",
    "AuditMiddleware",
    "DATA_RETENTION_AUDIT_COUNTER",
    "DATA_RETENTION_TRANSACTION_COUNTER",
    "PrometheusMiddleware",
    "QUEUE_DEPTH_GAUGE",
    "REQUEST_COUNTER",
    "REQUEST_ERROR_COUNTER",
    "REQUEST_LATENCY_SECONDS",
    "metrics_router",
    "report_queue_depth",
    "initialise_tracing",
    "inject_traceparent",
    "instrument_fastapi_app",
    "instrument_sqlalchemy_engine",
    "span_from_traceparent",
]

"""Shared observability helpers for worker processes."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from opentelemetry import trace
from opentelemetry.trace import Span

from app.core.config import get_settings
from app.obs import initialise_tracing, report_queue_depth, span_from_traceparent


def configure_worker(service_name: str, *, queues: Sequence[str] | None = None) -> None:
    """Initialise tracing and register queue metrics for a worker service."""

    settings = get_settings()
    if settings.enable_tracing:
        initialise_tracing(
            service_name=service_name,
            endpoint=settings.otel_exporter_endpoint,
            instrument_logging=False,
        )
    if settings.enable_metrics and queues:
        for queue in queues:
            report_queue_depth(queue, 0)


@contextmanager
def worker_span(name: str, traceparent: str | None = None, **attributes: Any) -> Iterator[Span]:
    """Context manager that starts a worker span and attaches optional attributes."""

    with span_from_traceparent(name, traceparent, **attributes) as span:
        yield span


def current_traceparent() -> str | None:
    """Return a ``traceparent`` string for propagation to downstream systems."""

    span = trace.get_current_span()
    if span is None or span.get_span_context().trace_id == 0:
        return None
    carrier: dict[str, str] = {}
    from app.obs import inject_traceparent  # Local import to avoid circular deps

    populated = inject_traceparent(carrier)
    return populated.get("traceparent")


__all__ = ["configure_worker", "worker_span", "current_traceparent"]

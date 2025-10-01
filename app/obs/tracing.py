"""OpenTelemetry tracing helpers for API and worker services."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

try:  # pragma: no cover - exporter may not be available in minimal environments
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
except ModuleNotFoundError:  # pragma: no cover - graceful fallback for missing extras
    OTLPSpanExporter = None  # type: ignore[assignment]

_SERVICE_NAME_ATTRIBUTE = "service.name"


def _create_tracer_provider(service_name: str, endpoint: str | None) -> TracerProvider:
    resource = Resource(attributes={_SERVICE_NAME_ATTRIBUTE: service_name})
    provider = TracerProvider(resource=resource)

    exporter = None
    if endpoint and OTLPSpanExporter is not None:
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    if exporter is not None:
        processor = BatchSpanProcessor(exporter)
    else:
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    return provider


def initialise_tracing(
    *,
    service_name: str,
    endpoint: str | None = None,
    instrument_logging: bool = True,
) -> None:
    """Initialise a global tracer provider if one has not already been configured."""

    current_provider = trace.get_tracer_provider()
    if (
        isinstance(current_provider, TracerProvider)
        and getattr(current_provider.resource, "attributes", {}).get(_SERVICE_NAME_ATTRIBUTE)
        == service_name
    ):
        return

    provider = _create_tracer_provider(service_name, endpoint)
    trace.set_tracer_provider(provider)
    if instrument_logging:
        LoggingInstrumentor().instrument(set_logging_format=True)


def instrument_fastapi_app(app: FastAPI) -> None:
    """Enable FastAPI OpenTelemetry instrumentation."""
    FastAPIInstrumentor().instrument_app(app)


def instrument_sqlalchemy_engine(engine: Any) -> None:
    """Instrument SQLAlchemy engine for tracing if not already instrumented."""
    SQLAlchemyInstrumentor().instrument(engine=engine)


@contextmanager
def span_from_traceparent(name: str, traceparent: str | None, **attributes: Any) -> Iterator[Span]:
    """Create a span using an incoming ``traceparent`` header if provided."""

    tracer = trace.get_tracer(__name__)
    context = None
    if traceparent:
        carrier = {"traceparent": traceparent}
        context = TraceContextTextMapPropagator().extract(carrier=carrier)
    with tracer.start_as_current_span(name, context=context) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span


def inject_traceparent(headers: dict[str, str]) -> dict[str, str]:
    """Inject the current trace context into a carrier compatible with messaging systems."""

    carrier: dict[str, str] = dict(headers)
    TraceContextTextMapPropagator().inject(carrier)
    return carrier


__all__ = [
    "initialise_tracing",
    "instrument_fastapi_app",
    "instrument_sqlalchemy_engine",
    "inject_traceparent",
    "span_from_traceparent",
]

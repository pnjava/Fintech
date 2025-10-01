"""FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import register_routes
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.obs import (
    AuditMiddleware,
    PrometheusMiddleware,
    initialise_tracing,
    instrument_fastapi_app,
    metrics_router,
)


def create_application(settings: Settings | None = None) -> FastAPI:
    """Application factory used by ASGI servers and tests."""
    configure_logging()
    settings = settings or get_settings()

    if settings.enable_tracing:
        initialise_tracing(service_name=settings.app_name, endpoint=settings.otel_exporter_endpoint)

    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
    )

    application.add_middleware(AuditMiddleware, settings=settings)
    if settings.enable_metrics:
        application.add_middleware(PrometheusMiddleware)
        application.include_router(metrics_router)
    register_routes(application)

    if settings.enable_tracing:
        instrument_fastapi_app(application)

    return application


app = create_application()

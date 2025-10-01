"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings


def create_application() -> FastAPI:
    """Application factory that wires dependencies and routers."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.debug,
    )

    register_health_endpoints(app)
    register_placeholder_routes(app)

    return app


def register_health_endpoints(app: FastAPI) -> None:
    """Add health and readiness endpoints to the application."""

    @app.get("/healthz", tags=["observability"], response_class=JSONResponse)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["observability"], response_class=JSONResponse)
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}


def register_placeholder_routes(app: FastAPI) -> None:
    """Register placeholder business routes for future expansion."""

    router = APIRouter(prefix="/api/v1", tags=["placeholder"])

    @router.get("/placeholder", response_class=JSONResponse)
    async def placeholder() -> dict[str, str]:
        return {"message": "New features coming soon"}

    app.include_router(router)


app = create_application()


__all__ = ["app", "create_application"]

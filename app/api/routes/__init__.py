"""Top level API router registration."""
from fastapi import APIRouter, FastAPI

from app.api.routes import auth, health


def register_routes(application: FastAPI) -> None:
    """Register all API routers with the FastAPI application."""
    api_router = APIRouter(prefix="/api")

    api_router.include_router(health.router, tags=["health"])
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

    application.include_router(api_router)


__all__ = ["register_routes"]

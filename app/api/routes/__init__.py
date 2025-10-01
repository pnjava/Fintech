"""Top level API router registration."""
from fastapi import APIRouter, FastAPI

from app.api.routes import auth, dividends, health, plans, proxy, shareholders, transactions


def register_routes(application: FastAPI) -> None:
    """Register all API routers with the FastAPI application."""
    api_router = APIRouter(prefix="/api")

    api_router.include_router(health.router, tags=["health"])
    api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
    api_router.include_router(plans.router, tags=["plans"])
    api_router.include_router(shareholders.router, prefix="/shareholders", tags=["shareholders"])
    api_router.include_router(dividends.router, tags=["dividends"])
    api_router.include_router(proxy.router, tags=["proxy"])
    api_router.include_router(transactions.router, tags=["transactions"])

    application.include_router(api_router)


__all__ = ["register_routes"]

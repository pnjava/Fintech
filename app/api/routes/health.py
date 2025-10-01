"""Health and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/healthz", summary="Liveness check")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app_name}


@router.get("/readyz", summary="Readiness check")
def readiness_check() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ready", "service": settings.app_name}

"""Authentication endpoints for issuing JWTs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.core.config import Settings, get_settings

router = APIRouter()
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _create_token(
    *,
    subject: str,
    settings: Settings,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    now = datetime.utcnow()
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
        "tid": settings.default_tenant_id,
        "role": settings.default_role,
        "type": token_type,
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=TokenResponse, summary="Issue JWT access tokens")
def login(request: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if not password_context.verify(request.password, settings.default_user_hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = _create_token(
        subject=request.email,
        settings=settings,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
    )

    refresh_token = _create_token(
        subject=request.email,
        settings=settings,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )

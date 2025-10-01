"""Authentication endpoints for issuing JWTs."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Literal, cast
from uuid import uuid4

import bcrypt
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings

RoleName = Literal["ADMIN", "EMPLOYEE", "COMPLIANCE", "OPS"]
ROLE_VALUES: set[str] = {"ADMIN", "EMPLOYEE", "COMPLIANCE", "OPS"}

router = APIRouter()
security_scheme = HTTPBearer(auto_error=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: str
    password: str
    role: RoleName | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    tid: str
    role: RoleName
    type: Literal["access", "refresh"]
    iat: datetime
    exp: datetime
    jti: str


@dataclass(frozen=True)
class AuthenticatedUser:
    email: str
    tenant_id: str
    role: RoleName
    token_id: str


class RefreshTokenStore:
    """In-memory store tracking active and blacklisted refresh tokens."""

    def __init__(self) -> None:
        self._active: dict[str, str] = {}
        self._blacklist: set[str] = set()
        self._lock = Lock()

    def mark_active(self, subject: str, token_id: str) -> None:
        with self._lock:
            self._active[subject] = token_id

    def is_active(self, subject: str, token_id: str) -> bool:
        with self._lock:
            if token_id in self._blacklist:
                return False
            return self._active.get(subject) == token_id

    def blacklist(self, token_id: str) -> None:
        with self._lock:
            self._blacklist.add(token_id)

    def is_blacklisted(self, token_id: str) -> bool:
        with self._lock:
            return token_id in self._blacklist

    def reset(self) -> None:
        with self._lock:
            self._active.clear()
            self._blacklist.clear()


refresh_token_store = RefreshTokenStore()


def _create_token(
    *,
    subject: str,
    settings: Settings,
    expires_delta: timedelta,
    token_type: Literal["access", "refresh"],
    tenant_id: str,
    role: RoleName,
    signing_key: Any,
) -> tuple[str, str]:
    now = datetime.now(UTC)
    token_id = uuid4().hex
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "tid": tenant_id,
        "role": role,
        "type": token_type,
        "jti": token_id,
    }
    encoded = jwt.encode(payload, signing_key, algorithm=settings.jwt_algorithm)
    return encoded, token_id


def _issue_tokens(
    *,
    subject: str,
    settings: Settings,
    role: RoleName,
    tenant_id: str,
) -> tuple[TokenResponse, str]:
    signing_key = _load_signing_key(settings)
    access_token, _ = _create_token(
        subject=subject,
        settings=settings,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        token_type="access",
        tenant_id=tenant_id,
        role=role,
        signing_key=signing_key,
    )
    refresh_token, refresh_id = _create_token(
        subject=subject,
        settings=settings,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        token_type="refresh",
        tenant_id=tenant_id,
        role=role,
        signing_key=signing_key,
    )

    response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return response, refresh_id


def _decode_token(*, token: str, settings: Settings) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_private_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:  # pragma: no cover - jose normalizes errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    try:
        validated = TokenPayload(**payload)
    except ValidationError as exc:  # pragma: no cover - validation handles data issues
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    return validated


def _load_signing_key(settings: Settings) -> Any:
    try:
        return serialization.load_pem_private_key(
            settings.jwt_private_key.encode("utf-8"),
            password=None,
        )
    except ValueError as exc:  # pragma: no cover - configuration issue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid JWT signing key",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> AuthenticatedUser:
    settings = get_settings()
    payload = _decode_token(token=credentials.credentials, settings=settings)
    if payload.type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return AuthenticatedUser(
        email=payload.sub,
        tenant_id=payload.tid,
        role=payload.role,
        token_id=payload.jti,
    )


def require_role(*roles: RoleName) -> Callable[..., AuthenticatedUser]:
    allowed_roles: set[str] = set(roles)

    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


@router.post("/login", response_model=TokenResponse, summary="Issue JWT access tokens")
def login(request: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if "@" not in request.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email address",
        )
    password_valid = _verify_password(request.password, settings.default_user_hashed_password)
    if not password_valid and request.password != settings.default_user_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    role_value = request.role or settings.default_role
    if role_value not in ROLE_VALUES:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Invalid role configuration"
        if request.role is not None:
            status_code = status.HTTP_400_BAD_REQUEST
            detail = "Invalid role selection"
        raise HTTPException(status_code=status_code, detail=detail)
    role = cast(RoleName, role_value)
    response, refresh_id = _issue_tokens(
        subject=request.email,
        settings=settings,
        role=role,
        tenant_id=settings.default_tenant_id,
    )
    refresh_token_store.mark_active(request.email, refresh_id)
    return response


@router.post("/refresh", response_model=TokenResponse, summary="Rotate JWT refresh tokens")
def refresh_token(request: RefreshRequest) -> TokenResponse:
    settings = get_settings()
    payload = _decode_token(token=request.refresh_token, settings=settings)
    if payload.type != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
    if not refresh_token_store.is_active(payload.sub, payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    refresh_token_store.blacklist(payload.jti)
    response, refresh_id = _issue_tokens(
        subject=payload.sub,
        settings=settings,
        role=payload.role,
        tenant_id=payload.tid,
    )
    refresh_token_store.mark_active(payload.sub, refresh_id)
    return response


@router.get("/admin-area", summary="Protected resource accessible to admins only")
def admin_area(user: AuthenticatedUser = Depends(require_role("ADMIN"))) -> dict[str, str]:
    return {"subject": user.email, "role": user.role}


@router.get(
    "/employee-area",
    summary="Protected resource accessible to employees and admins",
)
def employee_area(
    user: AuthenticatedUser = Depends(require_role("EMPLOYEE", "ADMIN")),
) -> dict[str, str]:
    return {"subject": user.email, "role": user.role}


def _verify_password(raw_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:  # pragma: no cover - invalid hash format
        return False

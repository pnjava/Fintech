"""Shareholder CRUD endpoints."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.auth import AuthenticatedUser, require_role
from app.models import Shareholder
from app.schemas.shareholder import ShareholderCreate, ShareholderRead, ShareholderUpdate

router = APIRouter()


def _ensure_shareholder_belongs_to_tenant(
    *, shareholder: Shareholder | None, tenant_id: str
) -> Shareholder:
    if shareholder is None or shareholder.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shareholder not found")
    return shareholder


@router.post("/", response_model=ShareholderRead, status_code=status.HTTP_201_CREATED)
def create_shareholder(
    payload: ShareholderCreate,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> ShareholderRead:
    shareholder = Shareholder(
        tenant_id=user.tenant_id,
        external_ref=payload.external_ref,
        full_name=payload.full_name,
        email=payload.email,
        phone_number=payload.phone_number,
        type=payload.type,
        total_shares=Decimal(payload.total_shares),
        profile=payload.profile,
    )

    session.add(shareholder)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shareholder with external reference already exists",
        ) from exc
    session.refresh(shareholder)
    return ShareholderRead.model_validate(shareholder)


@router.get("/", response_model=list[ShareholderRead])
def list_shareholders(
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE", "EMPLOYEE")),
) -> list[ShareholderRead]:
    statement = select(Shareholder).where(Shareholder.tenant_id == user.tenant_id).order_by(
        Shareholder.full_name
    )
    results = session.scalars(statement).all()
    return [ShareholderRead.model_validate(item) for item in results]


@router.get("/{shareholder_id}", response_model=ShareholderRead)
def get_shareholder(
    shareholder_id: str,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE", "EMPLOYEE")),
) -> ShareholderRead:
    shareholder = session.get(Shareholder, shareholder_id)
    shareholder = _ensure_shareholder_belongs_to_tenant(
        shareholder=shareholder, tenant_id=user.tenant_id
    )
    return ShareholderRead.model_validate(shareholder)


@router.put("/{shareholder_id}", response_model=ShareholderRead)
def update_shareholder(
    shareholder_id: str,
    payload: ShareholderUpdate,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> ShareholderRead:
    shareholder = session.get(Shareholder, shareholder_id)
    shareholder = _ensure_shareholder_belongs_to_tenant(
        shareholder=shareholder, tenant_id=user.tenant_id
    )

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        if field_name == "total_shares" and value is not None:
            setattr(shareholder, field_name, Decimal(value))
        else:
            setattr(shareholder, field_name, value)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shareholder with external reference already exists",
        ) from exc
    session.refresh(shareholder)
    return ShareholderRead.model_validate(shareholder)


@router.delete("/{shareholder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shareholder(
    shareholder_id: str,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> None:
    shareholder = session.get(Shareholder, shareholder_id)
    shareholder = _ensure_shareholder_belongs_to_tenant(
        shareholder=shareholder, tenant_id=user.tenant_id
    )
    session.delete(shareholder)
    session.commit()


__all__ = [
    "create_shareholder",
    "delete_shareholder",
    "get_shareholder",
    "list_shareholders",
    "router",
    "update_shareholder",
]

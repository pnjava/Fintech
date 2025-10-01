"""Transaction-related API routes."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.auth import AuthenticatedUser, require_role
from app.schemas.transaction import DisbursementRequest, DisbursementResponse
from app.services.disbursements import (
    DisbursementAdapterError,
    DisbursementConcurrencyError,
    DisbursementPayload,
    DisbursementService,
    ShareholderKYCError,
    ShareholderNotFoundError,
)

router = APIRouter(prefix="/transactions")


@router.post("/disburse", response_model=DisbursementResponse, status_code=status.HTTP_201_CREATED)
def create_disbursement(
    payload: DisbursementRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> DisbursementResponse:
    request_id = getattr(request.state, "request_id", None) or uuid4().hex
    request.state.request_id = request_id
    request.state.actor_email = user.email
    request.state.tenant_id = user.tenant_id

    service = DisbursementService(session)
    disbursement_payload = DisbursementPayload(
        shareholder_id=payload.shareholder_id,
        amount=Decimal(payload.amount),
        currency=payload.currency,
        memo=payload.memo,
        bank_account_number=payload.bank_account_number,
        bank_routing_number=payload.bank_routing_number,
    )

    try:
        transaction = service.disburse(
            tenant_id=user.tenant_id,
            payload=disbursement_payload,
            actor_email=user.email,
            request_id=request_id,
        )
    except ShareholderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ShareholderKYCError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DisbursementAdapterError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DisbursementConcurrencyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    response = DisbursementResponse(
        transaction_id=transaction.id,
        status=transaction.status,
        amount=Decimal(transaction.amount),
        currency=transaction.currency,
        shareholder_id=transaction.shareholder_id or "",
        lock_version=transaction.lock_version,
        request_id=request_id,
    )
    return response


__all__ = ["create_disbursement", "router"]

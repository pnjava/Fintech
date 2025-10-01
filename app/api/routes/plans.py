"""Plan enrollment and contribution endpoints."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.auth import AuthenticatedUser, require_role
from app.schemas import (
    PlanContributionRequest,
    PlanContributionResponse,
    PlanEnrollmentRequest,
    PlanRead,
)
from app.services.plans import (
    DuplicatePlanError,
    PlanNotFoundError,
    ShareholderNotFoundError,
    TenantTypeError,
    enroll_employee_plan,
    record_plan_contribution,
)

router = APIRouter(prefix="/plans")


@router.post("/enroll", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
def enroll_plan(
    payload: PlanEnrollmentRequest,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS")),
) -> PlanRead:
    """Enroll an employee in a plan for the authenticated tenant."""

    try:
        plan = enroll_employee_plan(
            session,
            tenant_id=user.tenant_id,
            employee_id=payload.employee_id,
            plan_type=payload.plan_type,
            shareholder_id=payload.shareholder_id,
            vesting_schedule=payload.vesting_schedule,
        )
    except ShareholderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicatePlanError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TenantTypeError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return PlanRead.model_validate(plan)


@router.post("/{plan_id}/contributions", response_model=PlanContributionResponse, status_code=status.HTTP_201_CREATED)
def record_contribution(
    plan_id: str,
    payload: PlanContributionRequest,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS")),
) -> PlanContributionResponse:
    """Record a plan contribution and return the updated totals."""

    amount = Decimal(payload.amount)

    try:
        result = record_plan_contribution(
            session,
            tenant_id=user.tenant_id,
            plan_id=plan_id,
            amount=amount,
            currency=payload.currency,
            reference=payload.reference,
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TenantTypeError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    response = PlanContributionResponse(
        plan=PlanRead.model_validate(result.plan),
        transaction_id=result.transaction.id,
        amount=Decimal(result.transaction.amount),
        currency=result.transaction.currency,
    )
    return response


__all__ = [
    "enroll_plan",
    "record_contribution",
    "router",
]


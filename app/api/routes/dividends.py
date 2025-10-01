"""Dividend scheduling endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.api.routes.auth import AuthenticatedUser, require_role
from app.models import Shareholder
from app.schemas.dividend import DividendScheduleRequest, DividendScheduleResponse
from app.services.dividends import DividendEvent, calculate_dividend, dividend_queue

router = APIRouter(prefix="/dividends")


@router.post("/schedule", response_model=DividendScheduleResponse)
def schedule_dividends(
    payload: DividendScheduleRequest,
    session: Session = Depends(get_db_session),
    user: AuthenticatedUser = Depends(require_role("ADMIN", "OPS", "COMPLIANCE")),
) -> DividendScheduleResponse:
    statement = select(Shareholder).where(Shareholder.tenant_id == user.tenant_id)
    shareholders = session.scalars(statement).all()

    events: list[DividendEvent] = []
    for holder in shareholders:
        amount = calculate_dividend(holder.total_shares, payload.dividend_rate)
        events.append(
            DividendEvent(
                tenant_id=user.tenant_id,
                shareholder_id=holder.id,
                total_shares=holder.total_shares,
                dividend_rate=payload.dividend_rate,
                amount=amount,
                record_date=payload.record_date,
                memo=payload.memo,
            )
        )

    dividend_queue.extend(events)
    return DividendScheduleResponse(scheduled_events=len(events))


__all__ = ["router", "schedule_dividends"]

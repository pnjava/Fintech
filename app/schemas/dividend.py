"""Schemas for dividend scheduling endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DividendScheduleRequest(BaseModel):
    dividend_rate: Decimal = Field(..., gt=Decimal("0"))
    record_date: date | None = None
    memo: str | None = Field(default=None, max_length=255)


class DividendEventPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    shareholder_id: str
    meeting_id: str | None = None
    total_shares: Decimal
    dividend_rate: Decimal
    amount: Decimal
    record_date: date | None = None
    memo: str | None = None


class DividendScheduleResponse(BaseModel):
    scheduled_events: int


__all__ = [
    "DividendEventPayload",
    "DividendScheduleRequest",
    "DividendScheduleResponse",
]

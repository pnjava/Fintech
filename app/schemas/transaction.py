"""Pydantic schemas for transaction resources."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import TransactionStatus


class DisbursementRequest(BaseModel):
    shareholder_id: str = Field(..., min_length=1, max_length=64)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    memo: str | None = Field(default=None, max_length=255)
    bank_account_number: str = Field(..., min_length=4, max_length=34)
    bank_routing_number: str = Field(..., min_length=4, max_length=9)


class DisbursementResponse(BaseModel):
    transaction_id: str
    shareholder_id: str
    amount: Decimal
    currency: str
    status: TransactionStatus
    lock_version: int
    request_id: str

    class Config:
        use_enum_values = True


__all__ = ["DisbursementRequest", "DisbursementResponse"]

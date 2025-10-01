"""Pydantic schemas for shareholder resources."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.shareholder import ShareholderType


class ShareholderBase(BaseModel):
    external_ref: str = Field(..., max_length=128)
    full_name: str = Field(..., max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone_number: str | None = Field(default=None, max_length=32)
    type: ShareholderType = Field(default=ShareholderType.INDIVIDUAL)
    total_shares: Decimal = Field(default=Decimal("0"))
    profile: dict | None = None


class ShareholderCreate(ShareholderBase):
    pass


class ShareholderUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone_number: str | None = Field(default=None, max_length=32)
    type: ShareholderType | None = None
    total_shares: Decimal | None = None
    profile: dict | None = None


class ShareholderRead(ShareholderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str


__all__ = [
    "ShareholderBase",
    "ShareholderCreate",
    "ShareholderRead",
    "ShareholderUpdate",
]

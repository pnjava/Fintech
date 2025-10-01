"""Reporting projection for transactions."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TransactionReport(Base):
    """Denormalized transaction facts used for reporting queries."""

    __tablename__ = "transaction_reports"

    transaction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    shareholder_id: Mapped[str | None] = mapped_column(String(36), index=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    reference: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = ["TransactionReport"]

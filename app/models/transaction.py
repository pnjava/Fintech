"""Transaction ORM model."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TransactionType(str, enum.Enum):
    DIVIDEND = "DIVIDEND"
    DISBURSE = "DISBURSE"
    CONTRIBUTION = "CONTRIBUTION"
    VESTING = "VESTING"


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class Transaction(TimestampMixin, Base):
    """Financial transaction tied to a tenant."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    shareholder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employee_plans.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type"), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status"), nullable=False, default=TransactionStatus.PENDING
    )
    reference: Mapped[str | None] = mapped_column(String(128))
    details: Mapped[dict | None] = mapped_column(JSON)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tenant = relationship("Tenant", back_populates="transactions")
    shareholder = relationship("Shareholder", back_populates="transactions")
    plan = relationship("EmployeePlan", back_populates="transactions")

    __mapper_args__ = {"version_id_col": lock_version}


__all__ = ["Transaction", "TransactionType", "TransactionStatus"]

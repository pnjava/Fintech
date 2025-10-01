"""Shareholder ORM model."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Boolean, ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ShareholderType(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    INSTITUTION = "INSTITUTION"


class Shareholder(TimestampMixin, Base):
    """Represents a shareholder record scoped to a tenant."""

    __tablename__ = "shareholders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_ref", name="uq_shareholders_tenant_external_ref"),
        Index("ix_shareholders_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    type: Mapped[ShareholderType] = mapped_column(
        SAEnum(ShareholderType, name="shareholder_type"),
        nullable=False,
        default=ShareholderType.INDIVIDUAL,
    )
    total_shares: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    profile: Mapped[dict | None] = mapped_column(JSON)
    kyc_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant = relationship("Tenant", back_populates="shareholders")
    plans = relationship("EmployeePlan", back_populates="shareholder")
    transactions = relationship("Transaction", back_populates="shareholder")
    proxy_ballots = relationship("ProxyBallot", back_populates="shareholder")


__all__ = ["Shareholder", "ShareholderType"]

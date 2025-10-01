"""Proxy ballot ORM model."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProxyBallot(TimestampMixin, Base):
    """Proxy voting record limited to a single tenant."""

    __tablename__ = "proxy_ballots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "meeting_id", "shareholder_id", name="uq_proxy_ballots_meeting_shareholder"
        ),
        Index("ix_proxy_ballots_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[str] = mapped_column(String(64), nullable=False)
    shareholder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shareholders.id", ondelete="CASCADE"), nullable=False
    )
    ballot_choices: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(String(128))

    tenant = relationship("Tenant", back_populates="proxy_ballots")
    shareholder = relationship("Shareholder", back_populates="proxy_ballots")


__all__ = ["ProxyBallot"]

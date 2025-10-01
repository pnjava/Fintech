"""Tenant ORM model."""
from __future__ import annotations

import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TenantType(str, enum.Enum):
    ISSUER = "ISSUER"
    SPONSOR = "SPONSOR"


class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class Tenant(TimestampMixin, Base):
    """Represents an isolated tenant within the platform."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[TenantType] = mapped_column(Enum(TenantType, name="tenant_type"), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenant_status"), nullable=False, default=TenantStatus.ACTIVE
    )

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    shareholders = relationship(
        "Shareholder", back_populates="tenant", cascade="all, delete-orphan"
    )
    plans = relationship(
        "EmployeePlan", back_populates="tenant", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "Transaction", back_populates="tenant", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="tenant", cascade="all, delete-orphan"
    )
    proxy_ballots = relationship(
        "ProxyBallot", back_populates="tenant", cascade="all, delete-orphan"
    )


__all__ = ["Tenant", "TenantType", "TenantStatus"]

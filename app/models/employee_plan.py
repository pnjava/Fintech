"""Employee plan ORM model."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PlanType(str, enum.Enum):
    ESPP = "ESPP"
    RSU = "RSU"
    401K = "401K"
    PENSION = "PENSION"


class EmployeePlanStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class EmployeePlan(TimestampMixin, Base):
    """Employee plan enrollment for a tenant."""

    __tablename__ = "employee_plans"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "employee_id", "plan_type", name="uq_employee_plans_tenant_employee_plan"
        ),
        Index("ix_employee_plans_tenant_id", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    shareholder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True
    )
    employee_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_type: Mapped[PlanType] = mapped_column(SAEnum(PlanType, name="plan_type"), nullable=False)
    status: Mapped[EmployeePlanStatus] = mapped_column(
        SAEnum(EmployeePlanStatus, name="employee_plan_status"), nullable=False, default=EmployeePlanStatus.ACTIVE
    )
    contribution_total: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    vesting_schedule: Mapped[dict | None] = mapped_column(JSON)

    tenant = relationship("Tenant", back_populates="plans")
    shareholder = relationship("Shareholder", back_populates="plans")
    transactions = relationship("Transaction", back_populates="plan")


__all__ = ["EmployeePlan", "PlanType", "EmployeePlanStatus"]

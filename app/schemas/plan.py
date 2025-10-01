"""Schemas for plan enrollment and contributions."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.employee_plan import EmployeePlanStatus, PlanType


class PlanEnrollmentRequest(BaseModel):
    """Payload for enrolling an employee into a plan."""

    shareholder_id: str | None = Field(default=None, description="Existing shareholder identifier")
    employee_id: str = Field(..., max_length=128, description="External employee identifier")
    plan_type: PlanType = Field(..., description="Plan type to enroll the employee in")
    vesting_schedule: dict | None = Field(
        default=None,
        description="Opaque vesting schedule definition stored on the plan record",
    )


class PlanRead(BaseModel):
    """Serialized representation of an enrolled employee plan."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    shareholder_id: str | None
    employee_id: str
    plan_type: PlanType
    status: EmployeePlanStatus
    contribution_total: Decimal
    vesting_schedule: dict | None


class PlanContributionRequest(BaseModel):
    """Contribution payload for an enrolled plan."""

    amount: Decimal = Field(..., gt=Decimal("0"), description="Contribution amount in plan currency")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    reference: str | None = Field(default=None, max_length=128)


class PlanContributionResponse(BaseModel):
    """Response returned after recording a contribution."""

    plan: PlanRead
    transaction_id: str
    amount: Decimal
    currency: str


__all__ = [
    "PlanContributionRequest",
    "PlanContributionResponse",
    "PlanEnrollmentRequest",
    "PlanRead",
]


"""Business logic for employee plan enrollment and contributions."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    EmployeePlan,
    EmployeePlanStatus,
    PlanType,
    Shareholder,
    Tenant,
    TenantType,
    Transaction,
    TransactionStatus,
    TransactionType,
)


class PlanError(RuntimeError):
    """Base exception for plan service errors."""


class DuplicatePlanError(PlanError):
    """Raised when attempting to enroll an employee in a duplicate plan."""


class ShareholderNotFoundError(PlanError):
    """Raised when the supplied shareholder identifier does not exist."""


class PlanNotFoundError(PlanError):
    """Raised when a plan identifier is missing or not in scope."""


class TenantTypeError(PlanError):
    """Raised when the tenant is not authorized for plan operations."""


@dataclass(slots=True, frozen=True)
class ContributionResult:
    """Return value for contribution recordings."""

    plan: EmployeePlan
    transaction: Transaction


@contextmanager
def _serializable_transaction(session: Session) -> None:
    """Context manager enforcing SERIALIZABLE isolation for the transaction."""

    bind = session.get_bind()
    if bind is None:
        raise RuntimeError("Session is not bound to an engine")

    dialect = bind.dialect.name
    if dialect == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    else:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise


def _ensure_sponsor_tenant(session: Session, *, tenant_id: str) -> None:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.type != TenantType.SPONSOR:
        raise TenantTypeError(f"Tenant '{tenant_id}' is not authorized for plan operations")


def _resolve_shareholder(session: Session, *, shareholder_id: str, tenant_id: str) -> Shareholder:
    shareholder = session.get(Shareholder, shareholder_id)
    if shareholder is None or shareholder.tenant_id != tenant_id:
        raise ShareholderNotFoundError(f"Shareholder '{shareholder_id}' was not found for tenant '{tenant_id}'")
    return shareholder


def enroll_employee_plan(
    session: Session,
    *,
    tenant_id: str,
    employee_id: str,
    plan_type: PlanType,
    shareholder_id: str | None,
    vesting_schedule: dict | None,
) -> EmployeePlan:
    """Enroll an employee in a plan with SERIALIZABLE isolation."""

    _ensure_sponsor_tenant(session, tenant_id=tenant_id)

    if shareholder_id is not None:
        _resolve_shareholder(session, shareholder_id=shareholder_id, tenant_id=tenant_id)

    with _serializable_transaction(session):
        plan = EmployeePlan(
            tenant_id=tenant_id,
            shareholder_id=shareholder_id,
            employee_id=employee_id,
            plan_type=plan_type,
            status=EmployeePlanStatus.ACTIVE,
            vesting_schedule=vesting_schedule,
        )

        session.add(plan)

        try:
            session.flush()
        except IntegrityError as exc:
            raise DuplicatePlanError("Employee already enrolled in plan type for tenant") from exc

    session.refresh(plan)
    return plan


def record_plan_contribution(
    session: Session,
    *,
    tenant_id: str,
    plan_id: str,
    amount: Decimal,
    currency: str,
    reference: str | None = None,
) -> ContributionResult:
    """Record a contribution for the given plan under SERIALIZABLE isolation."""

    _ensure_sponsor_tenant(session, tenant_id=tenant_id)

    with _serializable_transaction(session):
        plan = session.get(EmployeePlan, plan_id)
        if plan is None or plan.tenant_id != tenant_id:
            raise PlanNotFoundError(f"Plan '{plan_id}' was not found for tenant '{tenant_id}'")

        normalized_amount = amount.quantize(Decimal("0.01"))
        current_total = Decimal(plan.contribution_total or 0)
        plan.contribution_total = (current_total + normalized_amount).quantize(Decimal("0.01"))

        transaction = Transaction(
            tenant_id=tenant_id,
            shareholder_id=plan.shareholder_id,
            plan_id=plan.id,
            amount=normalized_amount,
            currency=currency,
            type=TransactionType.CONTRIBUTION,
            status=TransactionStatus.SETTLED,
            reference=reference,
            details={"source": "plan_contribution"},
        )

        session.add(transaction)
        session.flush()

    session.refresh(plan)
    session.refresh(transaction)
    return ContributionResult(plan=plan, transaction=transaction)


__all__ = [
    "ContributionResult",
    "DuplicatePlanError",
    "PlanError",
    "PlanNotFoundError",
    "ShareholderNotFoundError",
    "TenantTypeError",
    "enroll_employee_plan",
    "record_plan_contribution",
]


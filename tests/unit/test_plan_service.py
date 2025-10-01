from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import TextClause

from app.models import EmployeePlan, PlanType, Shareholder, ShareholderType
from app.services.plans import record_plan_contribution
from tests.conftest import TestingSessionLocal


def _bootstrap_plan(db_session: Session) -> EmployeePlan:
    shareholder = Shareholder(
        tenant_id="tenant-demo",
        external_ref="EMP-100",
        full_name="Concurrent Tester",
        type=ShareholderType.INDIVIDUAL,
    )
    db_session.add(shareholder)
    plan = EmployeePlan(
        tenant_id="tenant-demo",
        shareholder_id=shareholder.id,
        employee_id="concurrent-employee",
        plan_type=PlanType.RSU,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


def _run_contribution(plan_id: str, amount: Decimal) -> None:
    session = TestingSessionLocal()
    try:
        record_plan_contribution(
            session,
            tenant_id="tenant-demo",
            plan_id=plan_id,
            amount=amount,
            currency="USD",
        )
    finally:
        session.close()


def test_serializable_contributions_avoid_lost_updates(db_session: Session, monkeypatch) -> None:
    plan = _bootstrap_plan(db_session)

    statements: list[str] = []

    original_execute = Session.execute

    def tracking_execute(self: Session, statement, *args, **kwargs):
        if isinstance(statement, TextClause):
            statements.append(str(statement))
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", tracking_execute)

    for amount in (Decimal("50.00"), Decimal("25.00"), Decimal("10.00")):
        _run_contribution(plan.id, amount)

    db_session.refresh(plan)
    assert Decimal(plan.contribution_total) == Decimal("85.00")
    assert any("BEGIN IMMEDIATE" in statement for statement in statements)


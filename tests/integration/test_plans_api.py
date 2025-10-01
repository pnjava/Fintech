from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Shareholder, ShareholderType


def _create_shareholder(session: Session, tenant_id: str) -> Shareholder:
    shareholder = Shareholder(
        tenant_id=tenant_id,
        external_ref="EMP-001",
        full_name="Alice Employee",
        type=ShareholderType.INDIVIDUAL,
    )
    session.add(shareholder)
    session.commit()
    return shareholder


def test_plan_enrollment_flow(client, auth_headers, db_session: Session) -> None:
    shareholder = _create_shareholder(db_session, "tenant-demo")

    payload = {
        "shareholder_id": shareholder.id,
        "employee_id": "alice-employee",
        "plan_type": "RSU",
        "vesting_schedule": {"type": "cliff", "months": 12},
    }

    response = client.post("/api/plans/enroll", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["plan_type"] == "RSU"
    assert data["employee_id"] == "alice-employee"
    assert data["shareholder_id"] == shareholder.id


def test_duplicate_plan_enrollment_returns_conflict(client, auth_headers, db_session: Session) -> None:
    shareholder = _create_shareholder(db_session, "tenant-demo")

    payload = {
        "shareholder_id": shareholder.id,
        "employee_id": "duplicate-employee",
        "plan_type": "RSU",
    }

    first = client.post("/api/plans/enroll", json=payload, headers=auth_headers)
    assert first.status_code == 201

    second = client.post("/api/plans/enroll", json=payload, headers=auth_headers)
    assert second.status_code == 409


def test_plan_contribution_updates_total(client, auth_headers, db_session: Session) -> None:
    shareholder = _create_shareholder(db_session, "tenant-demo")

    enroll_payload = {
        "shareholder_id": shareholder.id,
        "employee_id": "contrib-employee",
        "plan_type": "401K",
    }
    enroll_response = client.post("/api/plans/enroll", json=enroll_payload, headers=auth_headers)
    plan_id = enroll_response.json()["id"]

    contribution_payload = {"amount": "150.00", "currency": "USD", "reference": "JAN-2024"}
    response = client.post(
        f"/api/plans/{plan_id}/contributions",
        json=contribution_payload,
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["plan"]["id"] == plan_id
    assert Decimal(payload["plan"]["contribution_total"]) == Decimal("150.00")
    assert Decimal(payload["amount"]) == Decimal("150.00")


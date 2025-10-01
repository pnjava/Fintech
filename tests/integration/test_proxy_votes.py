from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Shareholder, ShareholderType, Tenant, TenantType


def _create_shareholder(db_session: Session, tenant_id: str) -> Shareholder:
    shareholder = Shareholder(
        tenant_id=tenant_id,
        external_ref=f"REF-{tenant_id}",
        full_name=f"Holder {tenant_id}",
        email=f"holder-{tenant_id}@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("10"),
    )
    db_session.add(shareholder)
    db_session.commit()
    return shareholder


def test_submit_proxy_vote_and_summary(client, auth_headers, db_session: Session) -> None:
    shareholder = _create_shareholder(db_session, "tenant-demo")

    vote_payload = {
        "meeting_id": "annual-2024",
        "shareholder_id": shareholder.id,
        "ballot_choices": {"proposal-1": "FOR", "proposal-2": "AGAINST"},
        "submitted_by": "system",
    }

    create_response = client.post("/api/proxy/votes", json=vote_payload, headers=auth_headers)
    assert create_response.status_code == 201

    summary_response = client.get(
        "/api/proxy/votes/summary",
        params={"meeting_id": "annual-2024"},
        headers=auth_headers,
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["proposal-1"]["FOR"] == 1
    assert summary["total_ballots"] == 1


def test_proxy_vote_enforces_uniqueness(client, auth_headers, db_session: Session) -> None:
    shareholder = _create_shareholder(db_session, "tenant-demo")
    vote_payload = {
        "meeting_id": "special-1",
        "shareholder_id": shareholder.id,
        "ballot_choices": {"proposal": "FOR"},
    }

    first_response = client.post("/api/proxy/votes", json=vote_payload, headers=auth_headers)
    assert first_response.status_code == 201

    second_response = client.post("/api/proxy/votes", json=vote_payload, headers=auth_headers)
    assert second_response.status_code == 409


def test_proxy_vote_respects_tenant_isolation(client, auth_headers, db_session: Session) -> None:
    other_tenant = Tenant(id="tenant-z", name="Tenant Z", type=TenantType.ISSUER)
    db_session.add(other_tenant)
    db_session.commit()

    outsider = _create_shareholder(db_session, "tenant-z")

    payload = {
        "meeting_id": "tenant-z-meeting",
        "shareholder_id": outsider.id,
        "ballot_choices": {"proposal": "FOR"},
    }

    response = client.post("/api/proxy/votes", json=payload, headers=auth_headers)
    assert response.status_code == 404

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Shareholder, ShareholderType
from app.services.dividends import dividend_queue


def test_dividend_schedule_enqueues_per_shareholder(
    client, auth_headers, db_session: Session
) -> None:
    dividend_queue.clear()

    first = Shareholder(
        tenant_id="tenant-demo",
        external_ref="H1",
        full_name="Holder One",
        email="holder1@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("100"),
    )
    second = Shareholder(
        tenant_id="tenant-demo",
        external_ref="H2",
        full_name="Holder Two",
        email="holder2@example.com",
        type=ShareholderType.INSTITUTION,
        total_shares=Decimal("250"),
    )
    db_session.add_all([first, second])
    db_session.commit()

    response = client.post(
        "/api/dividends/schedule",
        json={"dividend_rate": "0.05", "memo": "Q1 distribution"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["scheduled_events"] == 2

    events = dividend_queue.list_events()
    assert {event.shareholder_id for event in events} == {first.id, second.id}
    amounts = {event.shareholder_id: event.amount for event in events}
    assert amounts[first.id] == Decimal("5.00")
    assert amounts[second.id] == Decimal("12.50")

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Shareholder, ShareholderType, Tenant, TenantType


def test_shareholder_crud_flow(client, auth_headers, db_session: Session) -> None:
    payload = {
        "external_ref": "INV-001",
        "full_name": "Alice Investor",
        "email": "alice@example.com",
        "phone_number": "555-0101",
        "type": ShareholderType.INDIVIDUAL.value,
        "total_shares": "150.5",
        "profile": {"segment": "retail"},
    }

    create_response = client.post("/api/shareholders", json=payload, headers=auth_headers)
    assert create_response.status_code == 201
    created = create_response.json()
    shareholder_id = created["id"]

    get_response = client.get(f"/api/shareholders/{shareholder_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["full_name"] == "Alice Investor"

    update_response = client.put(
        f"/api/shareholders/{shareholder_id}",
        json={"full_name": "Alice I. Investor", "total_shares": "200"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    assert Decimal(update_response.json()["total_shares"]) == Decimal("200")

    list_response = client.get("/api/shareholders", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == shareholder_id for item in list_response.json())

    delete_response = client.delete(f"/api/shareholders/{shareholder_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/shareholders/{shareholder_id}", headers=auth_headers)
    assert missing_response.status_code == 404


def test_cross_tenant_isolation(client, auth_headers, db_session: Session) -> None:
    other_tenant = Tenant(id="tenant-b", name="Tenant B", type=TenantType.ISSUER)
    db_session.add(other_tenant)
    db_session.commit()

    outsider = Shareholder(
        tenant_id="tenant-b",
        external_ref="EXT-002",
        full_name="Bob Outsider",
        email="bob@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("50"),
    )
    db_session.add(outsider)
    db_session.commit()

    response = client.get(f"/api/shareholders/{outsider.id}", headers=auth_headers)
    assert response.status_code == 404

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest
from jose import jwt

from app.api.routes.auth import refresh_token_store
from app.core.config import get_settings
from app.main import app

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

ADMIN_ROLE = "ADMIN"
EMPLOYEE_ROLE = "EMPLOYEE"


@pytest.fixture()
def client() -> Iterator["TestClient"]:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_refresh_store() -> None:
    refresh_token_store.reset()
    yield
    refresh_token_store.reset()


def _login(client: "TestClient", role: str | None = None) -> tuple[str, str]:
    payload: dict[str, str] = {
        "email": "user@example.com",
        "password": "changeme",
    }
    if role is not None:
        payload["role"] = role

    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    return body["access_token"], body["refresh_token"]


def test_login_returns_signed_tokens(client: "TestClient") -> None:
    access_token, refresh_token = _login(client, role=ADMIN_ROLE)

    settings = get_settings()
    access_payload = jwt.decode(
        access_token,
        settings.jwt_private_key,
        algorithms=[settings.jwt_algorithm],
    )
    refresh_payload = jwt.decode(
        refresh_token,
        settings.jwt_private_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert access_payload["sub"] == "user@example.com"
    assert access_payload["type"] == "access"
    assert access_payload["role"] == ADMIN_ROLE
    assert refresh_payload["type"] == "refresh"


def test_refresh_rotates_and_blacklists_tokens(client: "TestClient") -> None:
    _, refresh_token = _login(client, role=EMPLOYEE_ROLE)

    first_response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert first_response.status_code == 200
    first_body = first_response.json()
    new_refresh_token = first_body["refresh_token"]

    # Reusing the same refresh token should be rejected because of rotation
    second_response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert second_response.status_code == 401

    # The new refresh token should continue to work
    third_response = client.post("/api/auth/refresh", json={"refresh_token": new_refresh_token})
    assert third_response.status_code == 200


def test_admin_role_access_control(client: "TestClient") -> None:
    access_token, _ = _login(client, role=ADMIN_ROLE)

    headers = {"Authorization": f"Bearer {access_token}"}
    admin_response = client.get("/api/auth/admin-area", headers=headers)
    assert admin_response.status_code == 200

    employee_response = client.get("/api/auth/employee-area", headers=headers)
    assert employee_response.status_code == 200


def test_employee_role_access_control(client: "TestClient") -> None:
    access_token, _ = _login(client, role=EMPLOYEE_ROLE)

    headers = {"Authorization": f"Bearer {access_token}"}
    admin_response = client.get("/api/auth/admin-area", headers=headers)
    assert admin_response.status_code == 403

    employee_response = client.get("/api/auth/employee-area", headers=headers)
    assert employee_response.status_code == 200

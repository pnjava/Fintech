from __future__ import annotations

from decimal import Decimal
import json
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.models import AuditLog, Shareholder, ShareholderType, Transaction, TransactionStatus
from app.services.disbursements import (
    ACHDisbursementResponse,
    DisbursementConcurrencyError,
    DisbursementPayload,
    DisbursementService,
)
from tests.conftest import InMemoryS3Client, TestingSessionLocal


class DummyResponse:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:  # pragma: no cover - behaviour exercised implicitly
        return None

    def json(self) -> dict[str, str]:
        return self._payload


def test_disbursement_success_flow(
    client,
    db_session,
    auth_headers,
    audit_s3_client: InMemoryS3Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shareholder = Shareholder(
        tenant_id="tenant-demo",
        external_ref="EXT-123",
        full_name="Paula Payout",
        email="paula@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("100"),
        kyc_verified=True,
    )
    db_session.add(shareholder)
    db_session.commit()

    payload = {
        "shareholder_id": shareholder.id,
        "amount": "250.75",
        "currency": "USD",
        "memo": "Quarterly bonus",
        "bank_account_number": "123456789012",
        "bank_routing_number": "111000025",
    }

    def fake_post(*args, **kwargs):
        return DummyResponse({"reference": "ACH-123", "status": "ACCEPTED", "message": "queued"})

    monkeypatch.setattr("app.services.disbursements.httpx.post", fake_post)

    request_id = uuid4().hex
    response = client.post(
        "/api/transactions/disburse",
        headers={**auth_headers, "X-Request-ID": request_id},
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == TransactionStatus.SETTLED.value
    assert body["request_id"] == request_id

    transaction = db_session.get(Transaction, body["transaction_id"])
    assert transaction is not None
    assert transaction.status == TransactionStatus.SETTLED
    assert transaction.lock_version >= 2
    assert transaction.details is not None
    assert transaction.details["ach_request"]["account_last4"] == "9012"
    assert transaction.details["ach_response"]["reference"] == "ACH-123"

    audit_entry = db_session.query(AuditLog).first()
    assert audit_entry is not None
    assert audit_entry.payload["request_id"] == request_id
    assert audit_entry.payload["status"] == TransactionStatus.SETTLED.value

    settings = get_settings()
    bucket_contents = audit_s3_client.buckets.get(settings.audit_log_bucket, {})
    assert bucket_contents, "expected audit logs to be written to S3"
    key, data = next(iter(bucket_contents.items()))
    lines = [line for line in data.decode("utf-8").splitlines() if line]
    assert lines, "expected audit logs to be written to S3"
    last_entry = json.loads(lines[-1])
    assert last_entry["request_id"] == request_id
    assert last_entry["status"] == 201


def test_disbursement_requires_kyc(
    client,
    db_session,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shareholder = Shareholder(
        tenant_id="tenant-demo",
        external_ref="EXT-999",
        full_name="Kyc Pending",
        email="pending@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("10"),
        kyc_verified=False,
    )
    db_session.add(shareholder)
    db_session.commit()

    response = client.post(
        "/api/transactions/disburse",
        headers=auth_headers,
        json={
            "shareholder_id": shareholder.id,
            "amount": "20",
            "currency": "USD",
            "memo": "Incomplete",
            "bank_account_number": "444455556666",
            "bank_routing_number": "021000021",
        },
    )

    assert response.status_code == 400
    assert "KYC" in response.json()["detail"].upper()


class RacingAdapter:
    def submit(self, *, transaction: Transaction, request) -> ACHDisbursementResponse:
        other_session = TestingSessionLocal()
        try:
            competing = other_session.get(Transaction, transaction.id)
            assert competing is not None
            competing.status = TransactionStatus.FAILED
            competing.details = {"race": True}
            other_session.commit()
        finally:
            other_session.close()
        return ACHDisbursementResponse(reference="RACE", status="ACCEPTED", message="ok")


def test_disbursement_detects_concurrent_updates(db_session) -> None:
    shareholder = Shareholder(
        tenant_id="tenant-demo",
        external_ref="EXT-777",
        full_name="Concurrent Actor",
        email="actor@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("25"),
        kyc_verified=True,
    )
    db_session.add(shareholder)
    db_session.commit()

    service = DisbursementService(db_session, adapter=RacingAdapter())
    payload = DisbursementPayload(
        shareholder_id=shareholder.id,
        amount=Decimal("100"),
        currency="USD",
        memo="",
        bank_account_number="987654321000",
        bank_routing_number="026009593",
    )

    with pytest.raises(DisbursementConcurrencyError):
        service.disburse(
            tenant_id="tenant-demo",
            payload=payload,
            actor_email="ops@example.com",
            request_id="race",
        )

    db_session.rollback()
    transaction = db_session.query(Transaction).order_by(Transaction.created_at.desc()).first()
    assert transaction is not None
    assert transaction.status == TransactionStatus.FAILED

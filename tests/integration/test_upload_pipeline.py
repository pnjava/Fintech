from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import get_settings
from app.models import Shareholder, ShareholderType, TransactionReport
from app.services.disbursements import ACHDisbursementResponse, DisbursementPayload, DisbursementService
from app.services.transaction_events import TransactionEvent, TransactionEventConsumer
from app.services.uploads import ShareholderUploadMessage, ShareholderUploadService, process_upload_message
from tests.conftest import InMemoryS3Client, InMemorySQSClient, TestingSessionLocal


class AcceptingAdapter:
    def submit(self, *, transaction, request) -> ACHDisbursementResponse:  # type: ignore[override]
        return ACHDisbursementResponse(reference="OK", status="ACCEPTED", message="queued")


class FakeKafkaConsumer:
    def __init__(self, events: list[TransactionEvent]) -> None:
        self._events = events
        self.committed = False

    def poll(self, timeout_ms: int) -> dict[str, list[SimpleNamespace]]:
        if not self._events:
            return {}
        records = [SimpleNamespace(value=event.model_dump(mode="json")) for event in self._events]
        self._events = []
        return {"topic": records}

    def commit(self) -> None:
        self.committed = True


def test_upload_api_enqueues_validation_job(
    client,
    auth_headers,
    audit_s3_client: InMemoryS3Client,
    sqs_client: InMemorySQSClient,
) -> None:
    settings = get_settings()
    payload = "external_ref,name,holdings,email\nEXT-1,Alice,12.5,alice@example.com\n"

    response = client.post(
        "/api/uploads/shareholders",
        headers={
            **auth_headers,
            "Content-Type": "text/csv",
            "X-Upload-Filename": "shareholders.csv",
        },
        content=payload.encode("utf-8"),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"

    bucket_contents = audit_s3_client.buckets.get(settings.upload_bucket, {})
    assert bucket_contents
    key, data = next(iter(bucket_contents.items()))
    assert key.startswith(settings.upload_prefix)
    assert "EXT-1" in data.decode("utf-8")

    messages = sqs_client.queue(settings.upload_queue_url)
    assert messages
    message_payload = json.loads(messages[0]["Body"])
    assert message_payload["bucket"] == settings.upload_bucket
    assert message_payload["tenant_id"] == "tenant-demo"


def test_upload_validator_persists_valid_rows(
    db_session,
    audit_s3_client: InMemoryS3Client,
    sqs_client: InMemorySQSClient,
) -> None:
    settings = get_settings()
    key = f"{settings.upload_prefix}/tenant-demo/test.csv"
    body = (
        "external_ref,name,holdings,email\n"
        "EXT-10,Ada,25.5,ada@example.com\n"
        "EXT-11,Bob,invalid,bob@example.com\n"
    )
    audit_s3_client.put_object(
        Bucket=settings.upload_bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="text/csv",
    )

    message = ShareholderUploadMessage(
        upload_id=uuid4().hex,
        bucket=settings.upload_bucket,
        key=key,
        tenant_id="tenant-demo",
        content_type="text/csv",
        original_filename="test.csv",
        enqueued_at="2023-01-01T00:00:00Z",
    )

    service = ShareholderUploadService()
    result = process_upload_message(
        message=message,
        session_factory=TestingSessionLocal,
        service=service,
        s3_client=audit_s3_client,
        sqs_client=sqs_client,
        dead_letter_queue_url=settings.upload_dead_letter_queue_url,
    )

    assert result.processed == 1
    assert result.invalid == 1

    shareholder = (
        db_session.query(Shareholder)
        .filter(Shareholder.tenant_id == "tenant-demo", Shareholder.external_ref == "EXT-10")
        .one()
    )
    assert shareholder.full_name == "Ada"
    assert shareholder.email == "ada@example.com"

    invalid_queue = sqs_client.queue(settings.upload_dead_letter_queue_url)
    assert invalid_queue
    dead_letter_body = json.loads(invalid_queue[0]["Body"])
    assert dead_letter_body["upload_id"] == message.upload_id
    assert dead_letter_body["invalid_rows"]


def test_transaction_events_feed_reporting_table(
    db_session,
    transaction_events,
) -> None:
    shareholder = Shareholder(
        tenant_id="tenant-demo",
        external_ref="EXT-100",
        full_name="Event Driven",
        email="event@example.com",
        type=ShareholderType.INDIVIDUAL,
        total_shares=Decimal("100"),
        kyc_verified=True,
    )
    db_session.add(shareholder)
    db_session.commit()

    service = DisbursementService(db_session, adapter=AcceptingAdapter())
    payload = DisbursementPayload(
        shareholder_id=shareholder.id,
        amount=Decimal("50.00"),
        currency="USD",
        memo="Event Test",
        bank_account_number="111122223333",
        bank_routing_number="021000021",
    )
    transaction = service.disburse(
        tenant_id="tenant-demo",
        payload=payload,
        actor_email="ops@example.com",
        request_id="REQ-1",
    )

    assert transaction.status.value == "SETTLED"
    assert transaction_events  # ensure publisher invoked

    event = TransactionEvent.from_transaction(transaction=transaction, event_type="STATUS_CHANGED")
    consumer = TransactionEventConsumer(
        session_factory=TestingSessionLocal,
        consumer_factory=lambda: FakeKafkaConsumer([event]),
    )
    processed = consumer.poll_once()
    assert processed

    report = db_session.get(TransactionReport, transaction.id)
    assert report is not None
    assert report.status == transaction.status.value
    assert report.tenant_id == transaction.tenant_id
    assert Decimal(report.amount) == Decimal(str(transaction.amount))
    assert report.event_type == "STATUS_CHANGED"

    assert consumer._get_consumer().committed  # type: ignore[attr-defined]

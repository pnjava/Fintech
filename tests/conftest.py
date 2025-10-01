from __future__ import annotations

import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
import sys
from threading import Lock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.deps import get_db_session
from app.main import app
from app.main import app as fastapi_app
from app.models import Base, Tenant, TenantType
from app.obs import AuditMiddleware


class InMemoryS3Client:
    """Simple in-memory S3 stub used by the audit middleware during tests."""

    exceptions = SimpleNamespace(NoSuchKey=type("NoSuchKey", (Exception,), {}))

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, bytes]] = {}

    def head_bucket(self, *, Bucket: str) -> None:
        if Bucket not in self._buckets:
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")

    def create_bucket(self, *, Bucket: str, **_: object) -> None:
        self._buckets.setdefault(Bucket, {})

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, BytesIO]:
        if Bucket not in self._buckets:
            raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "GetObject")
        bucket = self._buckets[Bucket]
        if Key not in bucket:
            raise self.exceptions.NoSuchKey()
        return {"Body": BytesIO(bucket[Key])}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str | None = None,
        **_: object,
    ) -> dict[str, str]:
        bucket = self._buckets.setdefault(Bucket, {})
        if isinstance(Body, str):
            data = Body.encode("utf-8")
        else:
            data = Body
        bucket[Key] = data
        return {"ETag": "in-memory"}

    @property
    def buckets(self) -> dict[str, dict[str, bytes]]:
        return self._buckets


class InMemorySQSClient:
    """Naïve in-memory SQS stub for unit tests."""

    def __init__(self) -> None:
        self._queues: dict[str, list[dict[str, str]]] = {}
        self._lock = Lock()

    def send_message(self, *, QueueUrl: str, MessageBody: str, **_: object) -> dict[str, str]:
        with self._lock:
            queue = self._queues.setdefault(QueueUrl, [])
            message_id = uuid4().hex
            queue.append({"MessageId": message_id, "Body": MessageBody, "ReceiptHandle": ""})
            return {"MessageId": message_id}

    def receive_message(
        self,
        *,
        QueueUrl: str,
        MaxNumberOfMessages: int = 1,
        **_: object,
    ) -> dict[str, list[dict[str, str]]]:
        with self._lock:
            queue = self._queues.get(QueueUrl, [])
            if not queue:
                return {}
            messages: list[dict[str, str]] = []
            for entry in queue[:MaxNumberOfMessages]:
                if not entry["ReceiptHandle"]:
                    entry["ReceiptHandle"] = uuid4().hex
                messages.append(
                    {
                        "MessageId": entry["MessageId"],
                        "ReceiptHandle": entry["ReceiptHandle"],
                        "Body": entry["Body"],
                    }
                )
            return {"Messages": messages}

    def delete_message(self, *, QueueUrl: str, ReceiptHandle: str, **_: object) -> None:
        with self._lock:
            queue = self._queues.get(QueueUrl, [])
            for index, entry in enumerate(queue):
                if entry.get("ReceiptHandle") == ReceiptHandle:
                    queue.pop(index)
                    break

    def queue(self, queue_url: str) -> list[dict[str, str]]:
        with self._lock:
            return [dict(item) for item in self._queues.get(queue_url, [])]


DATABASE_URL = "sqlite+pysqlite:///./test_suite.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def audit_s3_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryS3Client]:
    client = InMemoryS3Client()

    def _client_factory(*args: object, **kwargs: object) -> InMemoryS3Client:
        return client

    monkeypatch.setattr("app.obs.audit.boto3.client", _client_factory)
    stack = getattr(fastapi_app, "middleware_stack", None)
    middleware = getattr(stack, "app", None)
    while middleware is not None and hasattr(middleware, "app"):
        if isinstance(middleware, AuditMiddleware):
            middleware._s3_client = None
            middleware._bucket_ready = False
        middleware = getattr(middleware, "app", None)
    yield client


@pytest.fixture()
def db_session() -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    tenant = Tenant(id="tenant-demo", name="Demo Tenant", type=TenantType.SPONSOR)
    session.add(tenant)
    session.commit()

    yield session
    session.close()


@pytest.fixture(autouse=True)
def _transaction_event_publisher_stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, str]]]:
    events: list[dict[str, str]] = []

    class StubPublisher:
        def __init__(self, *_: object, **__: object) -> None:
            self._events = events

        def publish(self, transaction, *, event_type: str) -> None:  # type: ignore[no-untyped-def]
            self._events.append(
                {
                    "transaction_id": transaction.id,
                    "tenant_id": transaction.tenant_id,
                    "event_type": event_type,
                    "status": transaction.status.value,
                }
            )

    class DummyKafkaProducer:
        def __init__(self, *_: object, **__: object) -> None:
            self.messages: list[dict[str, object]] = []

        def send(
            self,
            topic: str,
            value: dict[str, str],
            headers: list[tuple[str, bytes]] | None = None,
        ) -> None:
            self.messages.append({"topic": topic, "value": json.dumps(value), "headers": headers})

        def flush(self) -> None:  # pragma: no cover - compatibility shim
            return None

    class DummyKafkaConsumer:
        def __init__(self, *_: object, **__: object) -> None:
            self.committed = False

        def poll(self, timeout_ms: int) -> dict[str, list[dict[str, str]]]:  # pragma: no cover - default no-op
            return {}

        def commit(self) -> None:  # pragma: no cover - default no-op
            self.committed = True

    monkeypatch.setattr("app.services.disbursements.TransactionEventPublisher", StubPublisher)
    monkeypatch.setattr("app.services.transaction_events.TransactionEventPublisher", StubPublisher)
    monkeypatch.setattr("app.services.transaction_events.KafkaProducer", DummyKafkaProducer)
    monkeypatch.setattr("app.services.transaction_events.KafkaConsumer", DummyKafkaConsumer)
    yield events
    events.clear()


@pytest.fixture()
def transaction_events(_transaction_event_publisher_stub: list[dict[str, str]]) -> list[dict[str, str]]:
    return _transaction_event_publisher_stub


@pytest.fixture()
def sqs_client(
    monkeypatch: pytest.MonkeyPatch,
    audit_s3_client: InMemoryS3Client,
) -> Iterator[InMemorySQSClient]:
    client = InMemorySQSClient()

    def _client_factory(service_name: str, *args: object, **kwargs: object):
        if service_name == "s3":
            return audit_s3_client
        if service_name == "sqs":
            return client
        raise ValueError(f"Unsupported service: {service_name}")

    from importlib import import_module

    monkeypatch.setattr("app.services.uploads.boto3.client", _client_factory)

    upload_module = import_module("workers.upload_validator.main")
    monkeypatch.setattr(upload_module, "boto3", SimpleNamespace(client=_client_factory))
    yield client


@pytest.fixture()
def client(db_session: Session, audit_s3_client: InMemoryS3Client) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        try:
            yield db_session
        finally:
            db_session.rollback()

    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture()
def auth_headers(client: TestClient, audit_s3_client: InMemoryS3Client) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

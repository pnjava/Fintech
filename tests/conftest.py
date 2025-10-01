from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

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

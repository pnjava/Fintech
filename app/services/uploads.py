"""Services powering the shareholder upload pipeline."""
from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import boto3

try:  # pragma: no cover - optional dependency
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for testing
    class ValidationError(Exception):
        def __init__(self, message: str, path: list[str] | tuple[str, ...] = ()) -> None:
            super().__init__(message)
            self.message = message
            self.path = list(path)

    class Draft202012Validator:  # type: ignore[override]
        def __init__(self, schema: dict[str, Any]) -> None:
            self._schema = schema

        def iter_errors(self, instance: dict[str, Any]):  # type: ignore[override]
            if not isinstance(instance, dict):
                yield ValidationError("Instance must be an object", path=())
                return

            for field in self._schema.get("required", []):
                if instance.get(field) in (None, ""):
                    yield ValidationError(f"'{field}' is a required property", path=(field,))

            holdings = instance.get("holdings")
            if holdings is not None and not isinstance(holdings, (int, float)):
                yield ValidationError("holdings must be a number", path=("holdings",))

            for field in ("name", "external_ref"):
                value = instance.get(field)
                if value is not None and not isinstance(value, str):
                    yield ValidationError(f"{field} must be a string", path=(field,))
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.obs import inject_traceparent
from app.models import Shareholder, ShareholderType

logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPES = {
    "application/json",
    "text/json",
}

_CSV_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
}

_SHAREHOLDER_UPLOAD_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ShareholderUpload",
    "type": "object",
    "properties": {
        "external_ref": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "email": {"type": "string", "format": "email"},
        "holdings": {"type": "number", "minimum": 0},
    },
    "required": ["external_ref", "name", "holdings"],
    "additionalProperties": True,
}


@dataclass(slots=True, frozen=True)
class ShareholderUploadMessage:
    """Payload enqueued to the validator worker."""

    upload_id: str
    bucket: str
    key: str
    tenant_id: str
    content_type: str
    original_filename: str | None
    enqueued_at: str
    traceparent: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "upload_id": self.upload_id,
                "bucket": self.bucket,
                "key": self.key,
                "tenant_id": self.tenant_id,
                "content_type": self.content_type,
                "original_filename": self.original_filename,
                "enqueued_at": self.enqueued_at,
                "traceparent": self.traceparent,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "ShareholderUploadMessage":
        payload = json.loads(data)
        return cls(
            upload_id=str(payload["upload_id"]),
            bucket=str(payload["bucket"]),
            key=str(payload["key"]),
            tenant_id=str(payload["tenant_id"]),
            content_type=str(payload["content_type"]),
            original_filename=payload.get("original_filename"),
            enqueued_at=str(payload.get("enqueued_at") or datetime.now(timezone.utc).isoformat()),
            traceparent=payload.get("traceparent"),
        )


@dataclass(slots=True, frozen=True)
class ShareholderUploadResult:
    """Response returned to the upload API."""

    upload_id: str
    location: str


class ShareholderUploadService:
    """Handles persistence of uploaded shareholder files and queue fan-out."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        s3_client_factory: Callable[[], Any] | None = None,
        sqs_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._s3_client_factory = s3_client_factory or self._default_s3_client
        self._sqs_client_factory = sqs_client_factory or self._default_sqs_client
        self._s3_client: Any | None = None
        self._sqs_client: Any | None = None
        self._validator = Draft202012Validator(_SHAREHOLDER_UPLOAD_SCHEMA)
        self._bucket_ready = False

    def _default_s3_client(self) -> Any:
        return boto3.client(
            "s3",
            region_name=self._settings.aws_region,
            endpoint_url=self._settings.s3_endpoint_url,
        )

    def _default_sqs_client(self) -> Any:
        return boto3.client(
            "sqs",
            region_name=self._settings.aws_region,
            endpoint_url=self._settings.sqs_endpoint_url,
        )

    def _ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        client = self._get_s3_client()
        bucket = self._settings.upload_bucket
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:  # pragma: no cover - client raises ClientError subclasses
            client.create_bucket(Bucket=bucket)
        self._bucket_ready = True

    def _get_s3_client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = self._s3_client_factory()
        return self._s3_client

    def _get_sqs_client(self) -> Any:
        if self._sqs_client is None:
            self._sqs_client = self._sqs_client_factory()
        return self._sqs_client

    def handle_upload(
        self,
        *,
        tenant_id: str,
        file_bytes: bytes,
        filename: str | None,
        content_type: str | None,
    ) -> ShareholderUploadResult:
        self._ensure_bucket()
        upload_id = uuid4().hex
        extension = ""
        if filename and "." in filename:
            extension = filename.rsplit(".", 1)[-1]
        key = (
            f"{self._settings.upload_prefix}/{tenant_id}/"
            f"{datetime.now(timezone.utc):%Y/%m/%d}/{upload_id}"
        )
        if extension:
            key = f"{key}.{extension}"

        s3_client = self._get_s3_client()
        s3_client.put_object(
            Bucket=self._settings.upload_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type or "application/octet-stream",
            Metadata={
                "tenant_id": tenant_id,
                "upload_id": upload_id,
                "filename": filename or "",
            },
        )

        message = ShareholderUploadMessage(
            upload_id=upload_id,
            bucket=self._settings.upload_bucket,
            key=key,
            tenant_id=tenant_id,
            content_type=content_type or "application/octet-stream",
            original_filename=filename,
            enqueued_at=datetime.now(timezone.utc).isoformat(),
            traceparent=inject_traceparent({}).get("traceparent"),
        )
        sqs_client = self._get_sqs_client()
        sqs_client.send_message(
            QueueUrl=self._settings.upload_queue_url,
            MessageBody=message.to_json(),
        )
        location = f"s3://{self._settings.upload_bucket}/{key}"
        logger.info(
            "queued shareholder upload",
            extra={"upload_id": upload_id, "location": location, "tenant_id": tenant_id},
        )
        return ShareholderUploadResult(upload_id=upload_id, location=location)

    def parse_rows(self, *, key: str, body: bytes, content_type: str) -> list[dict[str, Any]]:
        if content_type.lower() in _JSON_CONTENT_TYPES or key.lower().endswith(".json"):
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict) and "rows" in payload:
                payload = payload["rows"]
            if not isinstance(payload, list):
                raise ValueError("JSON upload payload must be a list of rows")
            rows = [self._normalize_row(row) for row in payload]
            return rows

        if content_type.lower() in _CSV_CONTENT_TYPES or key.lower().endswith(".csv"):
            text = body.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = [self._normalize_row(row) for row in reader]
            return rows

        raise ValueError(f"Unsupported content type '{content_type}' for upload validation")

    def _normalize_row(self, row: Any) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise ValueError("Upload rows must be objects")
        normalized: dict[str, Any] = dict(row)
        if "holdings" in normalized:
            value = normalized["holdings"]
            if isinstance(value, str):
                value = value.strip()
            try:
                normalized["holdings"] = float(value)
            except (TypeError, ValueError):
                normalized["holdings"] = value
        return normalized

    def validate_rows(self, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        valid: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []
        for row in rows:
            errors = sorted(self._validator.iter_errors(row), key=lambda e: e.path)
            if errors:
                invalid.append(
                    {
                        "row": row,
                        "errors": [self._format_error(error) for error in errors],
                    }
                )
            else:
                valid.append(row)
        return valid, invalid

    def _format_error(self, error: ValidationError) -> str:
        path = "->".join(str(part) for part in error.path)
        return f"{path or '<root>'}: {error.message}"

    def persist_valid_rows(
        self,
        *,
        session: Session,
        tenant_id: str,
        rows: list[dict[str, Any]],
    ) -> list[str]:
        persisted_ids: list[str] = []
        for row in rows:
            external_ref = str(row["external_ref"])
            statement = select(Shareholder).where(
                Shareholder.tenant_id == tenant_id, Shareholder.external_ref == external_ref
            )
            shareholder = session.scalar(statement)
            if shareholder is None:
                shareholder = Shareholder(
                    tenant_id=tenant_id,
                    external_ref=external_ref,
                    full_name=str(row["name"]),
                    email=row.get("email"),
                    total_shares=self._to_decimal(row.get("holdings", 0)),
                    type=ShareholderType.INDIVIDUAL,
                    kyc_verified=False,
                )
                session.add(shareholder)
            else:
                shareholder.full_name = str(row["name"])
                shareholder.email = row.get("email")
                shareholder.total_shares = self._to_decimal(row.get("holdings", shareholder.total_shares))
            session.flush()
            persisted_ids.append(shareholder.id)
        session.commit()
        return persisted_ids

    def _to_decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation as exc:
                raise ValueError(f"Invalid numeric value '{value}'") from exc
        raise ValueError(f"Unsupported numeric type '{type(value)}'")


@dataclass(slots=True, frozen=True)
class UploadProcessingResult:
    """Outcome of validating a single upload."""

    upload_id: str
    processed: int
    invalid: int


def process_upload_message(
    *,
    message: ShareholderUploadMessage,
    session_factory: Callable[[], Session],
    service: ShareholderUploadService,
    s3_client: Any,
    sqs_client: Any,
    dead_letter_queue_url: str,
) -> UploadProcessingResult:
    """Validate and persist data for a queued shareholder upload."""

    response = s3_client.get_object(Bucket=message.bucket, Key=message.key)
    body: bytes = response["Body"].read()
    rows = service.parse_rows(key=message.key, body=body, content_type=message.content_type)
    valid_rows, invalid_rows = service.validate_rows(rows)

    session = session_factory()
    try:
        persisted = service.persist_valid_rows(
            session=session, tenant_id=message.tenant_id, rows=valid_rows
        )
    finally:
        session.close()

    if invalid_rows:
        sqs_client.send_message(
            QueueUrl=dead_letter_queue_url,
            MessageBody=json.dumps(
                {
                    "upload_id": message.upload_id,
                    "invalid_rows": invalid_rows,
                }
            ),
        )
        logger.warning(
            "upload validation produced invalid rows",
            extra={"upload_id": message.upload_id, "invalid_count": len(invalid_rows)},
        )

    logger.info(
        "processed shareholder upload",
        extra={
            "upload_id": message.upload_id,
            "valid_rows": len(persisted),
            "invalid_rows": len(invalid_rows),
        },
    )

    return UploadProcessingResult(
        upload_id=message.upload_id,
        processed=len(persisted),
        invalid=len(invalid_rows),
    )


__all__ = [
    "ShareholderUploadMessage",
    "ShareholderUploadResult",
    "ShareholderUploadService",
    "UploadProcessingResult",
    "process_upload_message",
]

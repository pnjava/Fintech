"""Audit logging middleware and utilities."""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings

_SENSITIVE_KEYS = {
    "email",
    "phone",
    "phone_number",
    "account_number",
    "routing_number",
    "bank_account_number",
    "tax_id",
    "ssn",
}


def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _mask_value(value[key]) for key in value}
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    if isinstance(value, str):
        if "@" in value:
            name, _, domain = value.partition("@")
            hidden = name[0] + "***" if name else "***"
            return f"{hidden}@{domain}" if domain else "***@***"
        if value.isdigit() and len(value) > 4:
            return f"***{value[-4:]}"
    return value


def _mask_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in mapping.items():
        if key.lower() in _SENSITIVE_KEYS:
            if isinstance(value, str) and len(value) > 4:
                sanitized[key] = f"***{value[-4:]}"
            else:
                sanitized[key] = "***"
        else:
            sanitized[key] = _mask_value(value)
    return sanitized


@dataclass(slots=True)
class AuditLogRecord:
    """Structured log entry emitted by the middleware."""

    timestamp: str
    request_id: str
    method: str
    path: str
    status: int
    duration_ms: float
    actor: str | None
    tenant_id: str | None
    ip_address: str | None
    query: dict[str, Any]
    body: Any

    def to_json(self) -> str:
        payload = {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "actor": self.actor,
            "tenant_id": self.tenant_id,
            "ip_address": self.ip_address,
            "query": self.query,
            "body": self.body,
        }
        return json.dumps(payload, default=str)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.to_json())


class AuditMiddleware(BaseHTTPMiddleware):
    """Starlette middleware capturing audit trails for compliance."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        logger: logging.Logger | None = None,
        s3_client_factory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(app)
        self._settings = settings
        self._logger = logger or logging.getLogger("audit")
        self._s3_client_factory = s3_client_factory or self._default_client_factory
        self._s3_client: Any | None = None
        self._bucket_ready = False

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()

        body_bytes = await request.body()
        self._set_body(request, body_bytes)

        masked_body = None
        if body_bytes:
            try:
                parsed = json.loads(body_bytes)
                masked_body = _mask_value(parsed)
                if isinstance(parsed, dict):
                    masked_body = _mask_mapping(masked_body)
            except json.JSONDecodeError:
                masked_body = "<binary>"

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        actor = getattr(request.state, "actor_email", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        ip_address = request.client.host if request.client else None
        query_dict = _mask_mapping(dict(request.query_params.multi_items()))

        record = AuditLogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            actor=actor,
            tenant_id=tenant_id,
            ip_address=ip_address,
            query=query_dict,
            body=masked_body,
        )

        self._logger.info(record.to_json())
        self._persist_to_s3(record)

        response.headers["X-Request-ID"] = request_id
        return response

    def _default_client_factory(self) -> Any:
        return boto3.client(
            "s3",
            region_name=self._settings.aws_region,
            endpoint_url=self._settings.s3_endpoint_url,
        )

    def _get_s3_client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = self._s3_client_factory()
        return self._s3_client

    def _ensure_bucket(self, client: Any) -> None:
        if self._bucket_ready:
            return
        bucket = self._settings.audit_log_bucket
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError:
            create_params = {"Bucket": bucket}
            if self._settings.aws_region != "us-east-1" and self._settings.s3_endpoint_url is None:
                create_params["CreateBucketConfiguration"] = {"LocationConstraint": self._settings.aws_region}
            try:
                client.create_bucket(**create_params)
            except ClientError as exc:  # pragma: no cover - configuration issues
                self._logger.error("failed to create audit bucket", extra={"error": str(exc)})
                return
        self._bucket_ready = True

    def _persist_to_s3(self, record: AuditLogRecord) -> None:
        if self._settings.audit_log_sample_rate <= 0:
            return
        if self._settings.audit_log_sample_rate < 1 and random.random() > self._settings.audit_log_sample_rate:
            return

        try:
            client = self._get_s3_client()
        except Exception as exc:  # pragma: no cover - defensive guard
            self._logger.error("failed to obtain s3 client", extra={"error": str(exc)})
            return

        try:
            self._ensure_bucket(client)
            key = self._daily_key()
            try:
                existing = client.get_object(Bucket=self._settings.audit_log_bucket, Key=key)["Body"].read()
            except client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
                existing = b""
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey"}:
                    existing = b""
                else:
                    raise
            payload = record.to_json().encode("utf-8") + b"\n"
            client.put_object(
                Bucket=self._settings.audit_log_bucket,
                Key=key,
                Body=existing + payload,
                ContentType="application/json",
            )
        except Exception as exc:  # pragma: no cover - S3 connectivity issues
            self._logger.error("failed to persist audit record", extra={"error": str(exc)})

    def _daily_key(self) -> str:
        now = datetime.now(timezone.utc)
        prefix = self._settings.audit_log_prefix.rstrip("/")
        return f"{prefix}/{now:%Y/%m/%d}/audit.log"

    @staticmethod
    def _set_body(request: Request, body: bytes) -> None:
        async def receive() -> dict[str, Any]:
            nonlocal consumed
            if consumed:
                return {"type": "http.request", "body": b"", "more_body": False}
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        consumed = False
        request._receive = receive  # type: ignore[attr-defined]


__all__ = ["AuditLogRecord", "AuditMiddleware"]

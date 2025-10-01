"""Disbursement orchestration services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import Settings, get_settings
from app.models import AuditLog, Shareholder, Transaction, TransactionStatus, TransactionType


class DisbursementError(RuntimeError):
    """Base class for disbursement service errors."""


class ShareholderNotFoundError(DisbursementError):
    """Raised when the shareholder cannot be located for the tenant."""


class ShareholderKYCError(DisbursementError):
    """Raised when the shareholder has not passed required KYC checks."""


class DisbursementAdapterError(DisbursementError):
    """Raised when the external ACH adapter call fails."""


class DisbursementConcurrencyError(DisbursementError):
    """Raised when optimistic locking detects a concurrent update."""


@dataclass(slots=True, frozen=True)
class DisbursementPayload:
    """Input data for a disbursement request."""

    shareholder_id: str
    amount: Decimal
    currency: str
    memo: str | None
    bank_account_number: str
    bank_routing_number: str


@dataclass(slots=True, frozen=True)
class ACHDisbursementRequest:
    """Payload submitted to the ACH adapter."""

    tenant_id: str
    shareholder_id: str
    amount: Decimal
    currency: str
    account_number: str
    routing_number: str
    memo: str | None
    request_id: str

    def to_json(self) -> dict[str, str | float | None]:
        return {
            "tenant_id": self.tenant_id,
            "shareholder_id": self.shareholder_id,
            "amount": float(self.amount),
            "currency": self.currency,
            "account_number": self.account_number,
            "routing_number": self.routing_number,
            "memo": self.memo,
            "request_id": self.request_id,
        }

    def masked(self) -> dict[str, str | None]:
        account_last4 = self.account_number[-4:]
        routing = self.routing_number
        if len(routing) > 4:
            routing = f"{routing[:3]}***{routing[-1]}"
        else:
            routing = "***"
        return {
            "tenant_id": self.tenant_id,
            "shareholder_id": self.shareholder_id,
            "amount": f"{self.amount:.2f}",
            "currency": self.currency,
            "account_last4": account_last4,
            "routing": routing,
            "memo": self.memo,
            "request_id": self.request_id,
        }


@dataclass(slots=True, frozen=True)
class ACHDisbursementResponse:
    """Response returned from the ACH adapter."""

    reference: str
    status: str
    message: str | None = None

    @property
    def accepted(self) -> bool:
        value = self.status.upper()
        return value in {"ACCEPTED", "SETTLED", "SUCCESS"}

    def to_dict(self) -> dict[str, str | None]:
        return {"reference": self.reference, "status": self.status, "message": self.message}


class ACHAdapter(Protocol):
    """Protocol describing an ACH disbursement adapter."""

    def submit(self, *, transaction: Transaction, request: ACHDisbursementRequest) -> ACHDisbursementResponse:
        """Submit the disbursement request and return the adapter response."""


class HTTPACHAdapter:
    """HTTP client used to interact with a mock ACH adapter."""

    def __init__(self, *, endpoint: str, timeout_seconds: float) -> None:
        self._endpoint = endpoint
        self._timeout = timeout_seconds

    def submit(self, *, transaction: Transaction, request: ACHDisbursementRequest) -> ACHDisbursementResponse:
        try:
            response = httpx.post(self._endpoint, json=request.to_json(), timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors handled in tests via adapter error
            raise DisbursementAdapterError("Failed to call ACH adapter") from exc

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - invalid adapter response
            raise DisbursementAdapterError("Invalid ACH adapter response") from exc

        reference = payload.get("reference")
        status = payload.get("status")
        message = payload.get("message")
        if not reference or not status:
            raise DisbursementAdapterError("Incomplete ACH adapter response")
        return ACHDisbursementResponse(reference=str(reference), status=str(status), message=message)


class DisbursementService:
    """Coordinates disbursement transaction lifecycle."""

    _ALLOWED_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
        TransactionStatus.PENDING: {TransactionStatus.SENT},
        TransactionStatus.SENT: {TransactionStatus.SETTLED, TransactionStatus.FAILED},
    }

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        adapter: ACHAdapter | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._adapter = adapter or HTTPACHAdapter(
            endpoint=self._settings.ach_adapter_url,
            timeout_seconds=self._settings.ach_adapter_timeout_seconds,
        )

    def disburse(
        self,
        *,
        tenant_id: str,
        payload: DisbursementPayload,
        actor_email: str,
        request_id: str,
    ) -> Transaction:
        shareholder = self._session.get(Shareholder, payload.shareholder_id)
        if shareholder is None or shareholder.tenant_id != tenant_id:
            raise ShareholderNotFoundError(
                f"Shareholder '{payload.shareholder_id}' was not found for tenant '{tenant_id}'"
            )
        if not shareholder.kyc_verified:
            raise ShareholderKYCError("Shareholder has not completed KYC verification")

        normalized_amount = payload.amount.quantize(Decimal("0.01"))
        transaction = Transaction(
            tenant_id=tenant_id,
            shareholder_id=shareholder.id,
            amount=normalized_amount,
            currency=payload.currency,
            type=TransactionType.DISBURSE,
            status=TransactionStatus.PENDING,
            details={
                "memo": payload.memo,
                "request_id": request_id,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        self._session.add(transaction)
        self._session.flush()

        adapter_request = ACHDisbursementRequest(
            tenant_id=tenant_id,
            shareholder_id=shareholder.id,
            amount=normalized_amount,
            currency=payload.currency,
            account_number=payload.bank_account_number,
            routing_number=payload.bank_routing_number,
            memo=payload.memo,
            request_id=request_id,
        )

        self._transition(transaction, TransactionStatus.SENT, extra_details={"ach_request": adapter_request.masked()})
        self._session.commit()
        self._session.refresh(transaction)

        try:
            adapter_response = self._adapter.submit(transaction=transaction, request=adapter_request)
        except DisbursementAdapterError:
            self._session.refresh(transaction)
            self._transition(
                transaction,
                TransactionStatus.FAILED,
                extra_details={"error": "ACH adapter call failed"},
            )
            self._record_audit(
                transaction=transaction,
                status=TransactionStatus.FAILED,
                actor_email=actor_email,
                request_id=request_id,
                message="ACH adapter call failed",
            )
            self._session.commit()
            self._session.refresh(transaction)
            raise

        final_status = TransactionStatus.SETTLED if adapter_response.accepted else TransactionStatus.FAILED
        self._transition(
            transaction,
            final_status,
            extra_details={"ach_response": adapter_response.to_dict()},
        )

        self._record_audit(
            transaction=transaction,
            status=final_status,
            actor_email=actor_email,
            request_id=request_id,
            message=adapter_response.message,
        )

        self._session.commit()
        self._session.refresh(transaction)
        return transaction

    def _transition(
        self,
        transaction: Transaction,
        new_status: TransactionStatus,
        *,
        extra_details: dict | None = None,
    ) -> None:
        allowed = self._ALLOWED_TRANSITIONS.get(transaction.status, set())
        if new_status not in allowed:
            raise DisbursementError(
                f"Invalid status transition from {transaction.status} to {new_status}"
            )

        merged_details = dict(transaction.details or {})
        if extra_details:
            merged_details.update(extra_details)

        transaction.status = new_status
        transaction.details = merged_details
        try:
            self._session.flush()
        except StaleDataError as exc:
            self._session.rollback()
            raise DisbursementConcurrencyError("Transaction was modified concurrently") from exc

    def _record_audit(
        self,
        *,
        transaction: Transaction,
        status: TransactionStatus,
        actor_email: str,
        request_id: str,
        message: str | None,
    ) -> None:
        log = AuditLog(
            tenant_id=transaction.tenant_id,
            actor_id=None,
            action="transaction.disburse",
            resource_type="Transaction",
            resource_id=transaction.id,
            payload={
                "status": status.value,
                "amount": f"{Decimal(transaction.amount):.2f}",
                "currency": transaction.currency,
                "shareholder_id": transaction.shareholder_id,
                "actor_email": actor_email,
                "request_id": request_id,
                "message": message,
            },
            ip_address=None,
        )
        self._session.add(log)


__all__ = [
    "ACHDisbursementRequest",
    "ACHDisbursementResponse",
    "ACHAdapter",
    "DisbursementAdapterError",
    "DisbursementConcurrencyError",
    "DisbursementError",
    "DisbursementPayload",
    "DisbursementService",
    "HTTPACHAdapter",
    "ShareholderKYCError",
    "ShareholderNotFoundError",
]

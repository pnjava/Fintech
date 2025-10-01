"""Reporting services fed by transaction events."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import TransactionReport

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from app.services.transactions.events import TransactionEvent


class TransactionReportingService:
    """Applies transaction events to the reporting projection."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def apply_event(self, event: "TransactionEvent") -> TransactionReport:
        report = self._session.get(TransactionReport, event.transaction_id)
        amount = Decimal(event.amount)
        if report is None:
            report = TransactionReport(
                transaction_id=event.transaction_id,
                tenant_id=event.tenant_id,
                shareholder_id=event.shareholder_id,
                plan_id=event.plan_id,
                amount=amount,
                currency=event.currency,
                status=event.status,
                type=event.type,
                reference=event.reference,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
            )
            self._session.add(report)
        else:
            report.tenant_id = event.tenant_id
            report.shareholder_id = event.shareholder_id
            report.plan_id = event.plan_id
            report.amount = amount
            report.currency = event.currency
            report.status = event.status
            report.type = event.type
            report.reference = event.reference
            report.event_type = event.event_type
            report.occurred_at = event.occurred_at
        return report


__all__ = ["TransactionReportingService"]

"""Data retention utilities for compliance and privacy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AuditLog, Transaction


@dataclass(slots=True)
class DataRetentionReport:
    """Summary of a retention cycle."""

    audit_logs_deleted: int
    transactions_deleted: int

    def total_deleted(self) -> int:
        return self.audit_logs_deleted + self.transactions_deleted


class DataRetentionService:
    """Encapsulates data retention policies for databases and object storage."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()

    def purge_expired_records(self, *, now: datetime | None = None) -> DataRetentionReport:
        """Purge records that exceed configured retention windows."""

        current_time = now or datetime.now(timezone.utc)
        audit_cutoff = current_time - timedelta(days=self._settings.audit_log_retention_days)
        transaction_cutoff = current_time - timedelta(
            days=self._settings.transaction_retention_days
        )

        audit_result = self._session.execute(
            delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
        )
        transaction_result = self._session.execute(
            delete(Transaction).where(Transaction.created_at < transaction_cutoff)
        )

        deleted_audit = int(audit_result.rowcount or 0)
        deleted_transactions = int(transaction_result.rowcount or 0)

        return DataRetentionReport(
            audit_logs_deleted=deleted_audit,
            transactions_deleted=deleted_transactions,
        )

    def build_s3_lifecycle_policy(self) -> dict[str, object]:
        """Return a placeholder S3 lifecycle configuration for IaC pipelines."""

        return {
            "Rules": [
                {
                    "ID": "expire-audit-logs",
                    "Filter": {"Prefix": "audit/"},
                    "Status": "Enabled",
                    "Expiration": {"Days": self._settings.upload_retention_days},
                },
                {
                    "ID": "expire-shareholder-uploads",
                    "Filter": {"Prefix": self._settings.upload_prefix},
                    "Status": "Enabled",
                    "Expiration": {"Days": self._settings.upload_retention_days},
                },
            ]
        }


__all__ = ["DataRetentionReport", "DataRetentionService"]

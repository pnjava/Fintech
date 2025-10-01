from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AuditLog, Transaction, TransactionStatus, TransactionType
from app.services.data_retention import DataRetentionService


def _make_audit_log(session: Session, *, created_at: datetime) -> None:
    log = AuditLog(
        tenant_id="tenant-demo",
        actor_id=None,
        action="TEST",
        resource_type="demo",
        resource_id="1",
        payload={"field": "value"},
        ip_address="127.0.0.1",
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(log)


def _make_transaction(session: Session, *, created_at: datetime) -> None:
    txn = Transaction(
        tenant_id="tenant-demo",
        shareholder_id=None,
        plan_id=None,
        amount=100,
        currency="USD",
        type=TransactionType.DIVIDEND,
        status=TransactionStatus.SETTLED,
        reference="ref",
        details={},
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(txn)


def test_data_retention_deletes_expired_records(db_session: Session) -> None:
    now = datetime.now(tz=UTC)
    old_timestamp = now - timedelta(days=400)
    new_timestamp = now - timedelta(days=10)

    _make_audit_log(db_session, created_at=old_timestamp)
    _make_audit_log(db_session, created_at=new_timestamp)
    _make_transaction(db_session, created_at=old_timestamp)
    _make_transaction(db_session, created_at=new_timestamp)
    db_session.commit()

    service = DataRetentionService(session=db_session)
    report = service.purge_expired_records(now=now)
    db_session.commit()

    remaining_audit = db_session.query(AuditLog).count()
    remaining_transactions = db_session.query(Transaction).count()

    assert report.audit_logs_deleted == 1
    assert report.transactions_deleted == 1
    assert remaining_audit == 1
    assert remaining_transactions == 1


def test_s3_lifecycle_policy_uses_configured_prefix(db_session: Session) -> None:
    service = DataRetentionService(session=db_session)
    policy = service.build_s3_lifecycle_policy()

    rule_ids = {rule["ID"] for rule in policy["Rules"]}
    assert "expire-audit-logs" in rule_ids
    assert "expire-shareholder-uploads" in rule_ids

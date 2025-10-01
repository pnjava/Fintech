"""Asynchronous worker executing data retention policies."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.obs import DATA_RETENTION_AUDIT_COUNTER, DATA_RETENTION_TRANSACTION_COUNTER
from app.services.data_retention import DataRetentionService
from app.workers.observability import configure_worker, worker_span

LOGGER = logging.getLogger(__name__)


async def run_once(service: DataRetentionService) -> None:
    """Execute a single retention cycle."""

    with worker_span("data_retention.cycle"):
        report = service.purge_expired_records(now=datetime.now(tz=UTC))
        if report.audit_logs_deleted:
            DATA_RETENTION_AUDIT_COUNTER.inc(report.audit_logs_deleted)
        if report.transactions_deleted:
            DATA_RETENTION_TRANSACTION_COUNTER.inc(report.transactions_deleted)
        LOGGER.info(
            "data retention cycle complete",
            extra={
                "audit_logs_deleted": report.audit_logs_deleted,
                "transactions_deleted": report.transactions_deleted,
            },
        )


async def run() -> None:
    """Continuously run data retention cycles at the configured cadence."""

    settings = get_settings()
    configure_worker("data-retention-worker", queues=["data-retention"])
    interval = max(60, settings.data_retention_interval_seconds)
    LOGGER.info("starting data retention worker", extra={"interval_seconds": interval})
    while True:
        with SessionLocal() as session:  # type: ignore[attr-defined]
            service = DataRetentionService(session=session, settings=settings)
            await run_once(service)
            session.commit()
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown
        LOGGER.info("data retention worker stopped")


if __name__ == "__main__":
    main()

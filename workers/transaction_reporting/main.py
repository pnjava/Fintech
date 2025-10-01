"""Worker consuming Kafka transaction events into reporting tables."""

from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.obs import report_queue_depth
from app.services.transaction_events import TransactionEventConsumer
from app.workers.observability import configure_worker, worker_span

logger = logging.getLogger(__name__)
QUEUE_NAME = "transaction-events"


class TransactionReportingWorker:
    """Coordinates consumption of transaction events for reporting."""

    def __init__(self) -> None:
        self._consumer = TransactionEventConsumer(session_factory=SessionLocal)

    async def run_forever(self) -> None:
        logger.info("transaction reporting worker started")
        while True:
            with worker_span("transaction_reporting.poll"):
                processed = await asyncio.to_thread(self._consumer.poll_once)
                depth = 0 if processed else 1
                report_queue_depth(QUEUE_NAME, depth)
            if not processed:
                await asyncio.sleep(1)


async def run() -> None:
    configure_worker("transaction-reporting-worker", queues=[QUEUE_NAME])
    worker = TransactionReportingWorker()
    await worker.run_forever()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - signal handling for CLI
        logger.info("transaction reporting worker stopped")


if __name__ == "__main__":
    main()

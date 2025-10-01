"""Worker consuming Kafka transaction events into reporting tables."""
from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.services.transaction_events import TransactionEventConsumer

logger = logging.getLogger(__name__)


class TransactionReportingWorker:
    """Coordinates consumption of transaction events for reporting."""

    def __init__(self) -> None:
        self._consumer = TransactionEventConsumer(session_factory=SessionLocal)

    async def run_forever(self) -> None:
        logger.info("transaction reporting worker started")
        while True:
            processed = await asyncio.to_thread(self._consumer.poll_once)
            if not processed:
                await asyncio.sleep(1)


async def run() -> None:
    worker = TransactionReportingWorker()
    await worker.run_forever()


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - signal handling for CLI
        logger.info("transaction reporting worker stopped")


if __name__ == "__main__":
    main()

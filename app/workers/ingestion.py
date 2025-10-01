"""Placeholder worker module for ingestion pipeline."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_ingestion_worker() -> None:
    """Simulate a background worker that processes messages."""
    logger.info("Starting ingestion worker loop")
    while True:
        await asyncio.sleep(5)
        logger.debug("Polling queue for new messages")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_ingestion_worker())


if __name__ == "__main__":
    main()

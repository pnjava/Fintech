"""Dividend processing worker with observability instrumentation."""

from __future__ import annotations

import asyncio
import logging

from app.obs import report_queue_depth
from app.workers.observability import configure_worker, worker_span

LOGGER = logging.getLogger(__name__)
QUEUE_NAME = "dividend-distributions"


async def run() -> None:
    """Simulate long running dividend distribution processing."""

    configure_worker("dividend-worker", queues=[QUEUE_NAME])
    backlog = 0
    while True:
        with worker_span("dividend.tick", queue_depth=backlog):
            LOGGER.debug("processing dividend cycle", extra={"queue_depth": backlog})
            report_queue_depth(QUEUE_NAME, backlog)
            backlog = max(0, backlog - 1)
        await asyncio.sleep(60)


def main() -> None:
    """Entry point for the dividend worker."""

    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        LOGGER.info("dividend worker stopped")


if __name__ == "__main__":
    main()

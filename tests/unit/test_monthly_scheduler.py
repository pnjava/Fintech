from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from workers.monthly_scheduler import next_month_start, run_monthly_scheduler


def test_next_month_start_handles_year_rollover() -> None:
    current = datetime(2023, 12, 15, 10, 0, tzinfo=timezone.utc)
    expected = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert next_month_start(current) == expected


def test_scheduler_executes_callback_once() -> None:
    start = datetime(2024, 3, 18, 12, 0, tzinfo=timezone.utc)
    delays: list[float] = []
    executed = 0

    async def run() -> None:
        nonlocal executed

        async def fake_sleep(seconds: float) -> None:
            delays.append(seconds)

        async def callback() -> None:
            nonlocal executed
            executed += 1

        await run_monthly_scheduler(
            callback,
            now_fn=lambda: start,
            sleep_fn=fake_sleep,
            iterations=1,
        )

    asyncio.run(run())

    assert executed == 1
    assert delays == [((datetime(2024, 4, 1, tzinfo=timezone.utc) - start).total_seconds())]


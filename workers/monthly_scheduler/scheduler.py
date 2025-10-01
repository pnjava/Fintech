"""Stub monthly scheduler that will trigger vesting updates."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable


def next_month_start(reference: datetime) -> datetime:
    """Return the UTC timestamp for the start of the next month."""

    tz = reference.tzinfo or timezone.utc
    year = reference.year + (1 if reference.month == 12 else 0)
    month = 1 if reference.month == 12 else reference.month + 1
    return datetime(year, month, 1, tzinfo=tz)


async def run_monthly_scheduler(
    callback: Callable[[], Awaitable[None]],
    *,
    now_fn: Callable[[], datetime] | None = None,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    iterations: int | None = None,
) -> None:
    """Invoke ``callback`` once per month relative to ``now_fn``."""

    now_provider = now_fn or (lambda: datetime.now(timezone.utc))
    executed = 0

    while iterations is None or executed < iterations:
        now = now_provider()
        target = next_month_start(now)
        delay = max((target - now).total_seconds(), 0.0)
        await sleep_fn(delay)
        await callback()
        executed += 1


"""Dividend calculation utilities and in-memory scheduler."""
from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from typing import Iterable


@dataclass(frozen=True, slots=True)
class DividendEvent:
    tenant_id: str
    shareholder_id: str
    total_shares: Decimal
    dividend_rate: Decimal
    amount: Decimal
    record_date: date | None = None
    memo: str | None = None


def calculate_dividend(holdings: Decimal | int | float, rate: Decimal | int | float) -> Decimal:
    """Return the dividend amount rounded to two decimal places."""

    holdings_decimal = Decimal(str(holdings))
    rate_decimal = Decimal(str(rate))
    amount = holdings_decimal * rate_decimal
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class DividendEventQueue:
    """Thread-safe in-memory queue used for tests and local development."""

    def __init__(self) -> None:
        self._events: list[DividendEvent] = []
        self._lock = Lock()

    def enqueue(self, event: DividendEvent) -> None:
        with self._lock:
            self._events.append(event)

    def extend(self, events: Iterable[DividendEvent]) -> None:
        with self._lock:
            self._events.extend(events)

    def list_events(self) -> list[DividendEvent]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


dividend_queue = DividendEventQueue()


__all__ = ["DividendEvent", "DividendEventQueue", "calculate_dividend", "dividend_queue"]

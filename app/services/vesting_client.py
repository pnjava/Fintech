"""HTTP client wrapper for the Rust vesting service."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import httpx


ScheduleType = Literal["cliff", "graded"]


@dataclass(slots=True, frozen=True)
class VestingSchedulePayload:
    """Serializable schedule payload sent to the vesting service."""

    type: ScheduleType
    cliff_months: int
    total_months: int | None = None

    def to_dict(self) -> dict[str, int | str]:
        payload: dict[str, int | str] = {
            "type": self.type,
            "cliff_months": self.cliff_months,
        }
        if self.type == "graded":
            if self.total_months is None:
                msg = "graded schedules require total_months"
                raise ValueError(msg)
            payload["total_months"] = self.total_months
        return payload


@dataclass(slots=True, frozen=True)
class VestingCalculation:
    """Response payload returned by the vesting service."""

    vested_fraction: Decimal
    vested_amount: Decimal
    remaining_amount: Decimal


class VestingServiceClient:
    """Synchronous wrapper around the vesting HTTP API."""

    def __init__(self, base_url: str, *, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "VestingServiceClient":  # pragma: no cover - convenience
        return self

    def __exit__(self, *_args: object) -> None:  # pragma: no cover - convenience
        self.close()

    def calculate(
        self,
        *,
        total_amount: Decimal,
        months_elapsed: int,
        schedule: VestingSchedulePayload,
        timeout: float | None = 5.0,
    ) -> VestingCalculation:
        payload = {
            "total_amount": float(total_amount),
            "months_elapsed": months_elapsed,
            "schedule": schedule.to_dict(),
        }
        response = self._client.post(
            f"{self._base_url}/vesting/calculate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return VestingCalculation(
            vested_fraction=Decimal(str(data["vested_fraction"])),
            vested_amount=Decimal(str(data["vested_amount"])),
            remaining_amount=Decimal(str(data["remaining_amount"])),
        )


__all__ = [
    "ScheduleType",
    "VestingCalculation",
    "VestingSchedulePayload",
    "VestingServiceClient",
]


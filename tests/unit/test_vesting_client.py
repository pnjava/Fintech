from __future__ import annotations

from decimal import Decimal
import json

import httpx
import pytest

from app.services.vesting_client import (
    VestingCalculation,
    VestingSchedulePayload,
    VestingServiceClient,
)


def test_vesting_client_calculate_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["schedule"]["type"] == "cliff"
        assert payload["total_amount"] == 100.0
        return httpx.Response(
            200,
            json={
                "vested_fraction": 0.5,
                "vested_amount": 50.0,
                "remaining_amount": 50.0,
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    wrapper = VestingServiceClient("http://vesting", client=client)
    schedule = VestingSchedulePayload(type="cliff", cliff_months=12)
    result = wrapper.calculate(total_amount=Decimal("100"), months_elapsed=12, schedule=schedule)

    assert isinstance(result, VestingCalculation)
    assert result.vested_fraction == Decimal("0.5")
    assert result.vested_amount == Decimal("50.0")
    assert result.remaining_amount == Decimal("50.0")


def test_vesting_client_requires_total_months() -> None:
    schedule = VestingSchedulePayload(type="graded", cliff_months=12)
    with pytest.raises(ValueError):
        schedule.to_dict()


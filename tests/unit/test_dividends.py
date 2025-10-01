from decimal import Decimal

from app.services.dividends import calculate_dividend


def test_calculate_dividend_rounds_half_up() -> None:
    amount = calculate_dividend(Decimal("100.25"), Decimal("0.075"))
    assert amount == Decimal("7.52")


def test_calculate_dividend_accepts_float_inputs() -> None:
    amount = calculate_dividend(150, 0.1)
    assert amount == Decimal("15.00")

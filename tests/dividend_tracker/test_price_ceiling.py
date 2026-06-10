from datetime import UTC, datetime

import pandas as pd
import pytest

from dividend_tracker.dividend_data import DividendData, DividendDistribution
from dividend_tracker.price_ceiling import calculate_price_ceiling


def test_price_ceiling_trailing_uses_ttm():
    dividend_data = DividendData(
        ticker="EGIE3",
        yahoo_ticker="EGIE3.SA",
        current_price=40.0,
        trailing_annual_dividends=3.0,
        trailing_dy=0.075,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2026-01-10"), amount=1.0)
        ],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_price_ceiling(
        "EGIE3",
        min_dy=0.06,
        dividend_data=dividend_data,
        ceiling_method="trailing",
    )

    assert result.price_ceiling == 50.0
    assert result.current_dy == 0.075
    assert result.min_dy == 0.06
    assert result.ceiling_method == "trailing"
    assert result.dividend_base == 3.0
    assert result.dividend_base_label == "TTM"
    assert result.margin_pct == 0.25
    assert result.is_below_or_equal_ceiling is True


def test_calculate_price_ceiling_rejects_zero_min_dy():
    with pytest.raises(ValueError, match="min_dy"):
        calculate_price_ceiling("EGIE3", min_dy=0)


def test_calculate_price_ceiling_marks_above_ceiling():
    dividend_data = DividendData(
        ticker="VIVT3",
        yahoo_ticker="VIVT3.SA",
        current_price=60.0,
        trailing_annual_dividends=3.0,
        trailing_dy=0.05,
        distributions=[],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_price_ceiling("VIVT3", min_dy=0.06, dividend_data=dividend_data)

    assert result.price_ceiling == 50.0
    assert result.margin_pct == pytest.approx(-0.1666666667)
    assert result.is_below_or_equal_ceiling is False


def test_price_ceiling_average_6y_uses_mean(monkeypatch):
    dividend_data = DividendData(
        ticker="EGIE3",
        yahoo_ticker="EGIE3.SA",
        current_price=40.0,
        trailing_annual_dividends=3.0,
        trailing_dy=0.075,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2026-01-10"), amount=1.0)
        ],
        fetched_at=datetime.now(UTC),
    )

    monkeypatch.setattr(
        "dividend_tracker.price_ceiling.calculate_average_annual_dividend",
        lambda **kwargs: 2.4,
    )

    result = calculate_price_ceiling(
        "EGIE3",
        min_dy=0.06,
        dividend_data=dividend_data,
        ceiling_method="average_6y",
    )

    assert result.price_ceiling == pytest.approx(40.0)
    assert result.dividend_base == 2.4
    assert result.ceiling_method == "average_6y"
    assert result.dividend_base_label == "Media 6 anos"


def test_price_ceiling_result_includes_method_fields():
    result = calculate_price_ceiling(
        "EGIE3",
        min_dy=0.06,
        dividend_data=DividendData(
            ticker="EGIE3",
            yahoo_ticker="EGIE3.SA",
            current_price=40.0,
            trailing_annual_dividends=3.0,
            trailing_dy=0.075,
            distributions=[],
            fetched_at=datetime.now(UTC),
        ),
    )

    assert result.ceiling_method == "trailing"
    assert result.dividend_base == 3.0
    assert result.dividend_base_label == "TTM"


def test_price_ceiling_default_method_is_trailing():
    dividend_data = DividendData(
        ticker="PEP",
        yahoo_ticker="PEP",
        current_price=100.0,
        trailing_annual_dividends=4.0,
        trailing_dy=0.04,
        distributions=[],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_price_ceiling("PEP", min_dy=0.04, dividend_data=dividend_data)

    assert result.ceiling_method == "trailing"
    assert result.price_ceiling == 100.0

from datetime import UTC, datetime

import pandas as pd
import pytest

from dividend_tracker.dividend_data import DividendData, DividendDistribution
from dividend_tracker.price_ceiling import calculate_price_ceiling


def test_calculate_price_ceiling_from_ttm_dividends():
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

    result = calculate_price_ceiling("EGIE3", min_dy=0.06, dividend_data=dividend_data)

    assert result.price_ceiling == 50.0
    assert result.current_dy == 0.075
    assert result.min_dy == 0.06
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

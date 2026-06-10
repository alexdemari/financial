from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from dividend_tracker.dividend_data import (
    DividendCacheError,
    DividendData,
    DividendDistribution,
    calculate_average_annual_dividend,
    fetch_dividend_data,
    normalize_yahoo_ticker,
)


def test_normalize_yahoo_ticker_adds_sa_for_br():
    assert normalize_yahoo_ticker("egie3", br=True) == "EGIE3.SA"
    assert normalize_yahoo_ticker("EGIE3.SA", br=True) == "EGIE3.SA"
    assert normalize_yahoo_ticker("schd", br=False) == "SCHD"


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_downloads_and_caches(mock_yf, tmp_path: Path):
    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 50.0
    yf_ticker.dividends = pd.Series(
        [1.0, 1.5],
        index=pd.to_datetime(["2026-01-10", "2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("EGIE3", br=True, cache_dir=tmp_path)

    assert result.yahoo_ticker == "EGIE3.SA"
    assert result.current_price == 50.0
    assert result.trailing_annual_dividends == 2.5
    assert result.trailing_dy == 0.05
    assert (tmp_path / "EGIE3.csv").exists()
    mock_yf.Ticker.assert_called_once_with("EGIE3.SA")


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_uses_fresh_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    data = DividendData(
        ticker="SCHD",
        yahoo_ticker="SCHD",
        current_price=80.0,
        trailing_annual_dividends=3.2,
        trailing_dy=0.04,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2026-01-01"), amount=0.8)
        ],
        fetched_at=datetime.now(UTC),
    )
    from dividend_tracker.dividend_data import _write_cache

    _write_cache(cache_path, data)

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 80.0
    mock_yf.Ticker.assert_not_called()


def test_fetch_dividend_data_local_only_requires_cache(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        fetch_dividend_data("SCHD", cache_dir=tmp_path, local_only=True)


def test_fetch_dividend_data_local_only_reports_corrupted_cache(tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,not-a-date,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )

    with pytest.raises(DividendCacheError, match="Invalid dividend cache"):
        fetch_dividend_data("SCHD", cache_dir=tmp_path, local_only=True)


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_refreshes_stale_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,2026-01-01T00:00:00+00:00,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )
    old_timestamp = (datetime.now(UTC) - timedelta(days=2)).timestamp()
    cache_path.touch()
    import os

    os.utime(cache_path, (old_timestamp, old_timestamp))

    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 100.0
    yf_ticker.dividends = pd.Series(
        [2.0],
        index=pd.to_datetime(["2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 100.0
    mock_yf.Ticker.assert_called_once_with("SCHD")


@patch("dividend_tracker.dividend_data.yf")
def test_fetch_dividend_data_refetches_fresh_corrupted_cache(mock_yf, tmp_path: Path):
    cache_path = tmp_path / "SCHD.csv"
    cache_path.write_text(
        "ticker,yahoo_ticker,fetched_at,current_price,trailing_annual_dividends,trailing_dy,date,amount\n"
        "SCHD,SCHD,not-a-date,10,1,0.1,2026-01-01,1\n",
        encoding="utf-8",
    )

    yf_ticker = MagicMock()
    yf_ticker.fast_info.last_price = 100.0
    yf_ticker.dividends = pd.Series(
        [2.0],
        index=pd.to_datetime(["2026-04-10"]),
    )
    mock_yf.Ticker.return_value = yf_ticker

    result = fetch_dividend_data("SCHD", cache_dir=tmp_path)

    assert result.current_price == 100.0
    mock_yf.Ticker.assert_called_once_with("SCHD")


def test_calculate_average_annual_dividend_correct_mean():
    distributions = []
    annual_totals = {
        2021: 2.40,
        2022: 2.80,
        2023: 3.20,
        2024: 3.60,
        2025: 4.00,
        2026: 4.40,
    }
    for year, annual_total in annual_totals.items():
        for quarter in range(1, 5):
            distributions.append(
                DividendDistribution(
                    date=pd.Timestamp(f"{year}-{quarter * 3:02d}-10"),
                    amount=annual_total / 4,
                )
            )
    dividend_data = DividendData(
        ticker="PEP",
        yahoo_ticker="PEP",
        current_price=140.0,
        trailing_annual_dividends=4.4,
        trailing_dy=0.031,
        distributions=distributions,
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend("PEP", dividend_data=dividend_data)

    assert result == pytest.approx(3.40)


def test_calculate_average_annual_dividend_includes_zero_years():
    dividend_data = DividendData(
        ticker="EGIE3",
        yahoo_ticker="EGIE3.SA",
        current_price=40.0,
        trailing_annual_dividends=3.0,
        trailing_dy=0.075,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2021-03-10"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2022-03-10"), amount=2.0),
            DividendDistribution(date=pd.Timestamp("2024-03-10"), amount=4.0),
            DividendDistribution(date=pd.Timestamp("2026-03-10"), amount=5.0),
        ],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend("EGIE3", dividend_data=dividend_data)

    assert result == pytest.approx(2.0)


def test_calculate_average_annual_dividend_raises_on_insufficient_data():
    dividend_data = DividendData(
        ticker="NEW",
        yahoo_ticker="NEW",
        current_price=10.0,
        trailing_annual_dividends=1.0,
        trailing_dy=0.10,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2025-03-10"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2026-03-10"), amount=1.2),
        ],
        fetched_at=datetime.now(UTC),
    )

    with pytest.raises(ValueError, match="insufficient dividend history"):
        calculate_average_annual_dividend("NEW", dividend_data=dividend_data)


def test_calculate_average_annual_dividend_groups_by_calendar_year():
    dividend_data = DividendData(
        ticker="CAL",
        yahoo_ticker="CAL",
        current_price=10.0,
        trailing_annual_dividends=1.0,
        trailing_dy=0.10,
        distributions=[
            DividendDistribution(date=pd.Timestamp("2024-12-31"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2025-01-01"), amount=2.0),
            DividendDistribution(date=pd.Timestamp("2026-01-01"), amount=3.0),
        ],
        fetched_at=datetime.now(UTC),
    )

    result = calculate_average_annual_dividend(
        "CAL", years=3, dividend_data=dividend_data
    )

    assert result == pytest.approx(2.0)

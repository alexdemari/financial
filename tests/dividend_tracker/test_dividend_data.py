from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from dividend_tracker.dividend_data import (
    DividendCacheError,
    DividendData,
    DividendDistribution,
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

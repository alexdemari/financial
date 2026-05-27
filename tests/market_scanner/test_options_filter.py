"""Tests for options_filter module — uses mocked yfinance, no network calls."""

from unittest.mock import MagicMock, patch

import pandas as pd

from market_scanner.options_filter import (
    VERDICT_ERROR,
    VERDICT_GOOD,
    VERDICT_ILLIQUID,
    VERDICT_NO_OPTIONS,
    VERDICT_OK,
    _classify,
    fetch_options_liquidity,
    filter_tradeable,
)


def _make_chain(calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> MagicMock:
    chain = MagicMock()
    chain.calls = calls_df
    chain.puts = puts_df
    return chain


def _calls_df(strike: float, bid: float, ask: float, oi: int, vol: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "openInterest": oi,
                "volume": vol,
            }
        ]
    )


# --- _classify ---


def test_classify_good():
    assert _classify(6000, 300, 9.0) == VERDICT_GOOD


def test_classify_ok_oi_boundary():
    assert _classify(1000, 50, 20.0) == VERDICT_OK


def test_classify_illiquid_spread_too_wide():
    assert _classify(6000, 300, 25.0) == VERDICT_ILLIQUID


def test_classify_illiquid_low_oi():
    assert _classify(500, 300, 9.0) == VERDICT_ILLIQUID


def test_classify_none_spread_is_illiquid():
    assert _classify(10000, 500, None) == VERDICT_ILLIQUID


# --- fetch_options_liquidity ---


@patch("market_scanner.options_filter._YF_AVAILABLE", True)
@patch("market_scanner.options_filter.yf", new_callable=MagicMock)
def test_fetch_no_options(mock_yf):
    ticker = MagicMock()
    ticker.options = []
    mock_yf.Ticker.return_value = ticker

    result = fetch_options_liquidity([("AAPL", "bullish", "smc")])
    assert len(result) == 1
    assert result.iloc[0]["verdict"] == VERDICT_NO_OPTIONS


@patch("market_scanner.options_filter._YF_AVAILABLE", True)
@patch("market_scanner.options_filter.yf", new_callable=MagicMock)
def test_fetch_good_liquidity(mock_yf):
    calls = _calls_df(strike=150.0, bid=2.90, ask=3.10, oi=8000, vol=500)
    puts = _calls_df(strike=150.0, bid=2.80, ask=3.00, oi=3000, vol=200)

    ticker = MagicMock()
    ticker.options = ["2026-06-20"]
    ticker.fast_info.last_price = 151.0
    ticker.option_chain.return_value = _make_chain(calls, puts)
    mock_yf.Ticker.return_value = ticker

    result = fetch_options_liquidity([("AAPL", "bullish", "lux")])
    row = result.iloc[0]
    assert row["verdict"] == VERDICT_GOOD
    assert row["total_oi"] == 11000
    assert row["daily_vol"] == 700
    assert row["strategy"] == "lux"


@patch("market_scanner.options_filter._YF_AVAILABLE", True)
@patch("market_scanner.options_filter.yf", new_callable=MagicMock)
def test_fetch_deduplicates_symbols(mock_yf):
    ticker = MagicMock()
    ticker.options = []
    mock_yf.Ticker.return_value = ticker

    result = fetch_options_liquidity(
        [("AAPL", "bullish", "smc"), ("AAPL", "bearish", "lux")]
    )
    assert len(result) == 1
    assert result.iloc[0]["strategy"] == "smc"


@patch("market_scanner.options_filter._YF_AVAILABLE", True)
@patch("market_scanner.options_filter.yf", new_callable=MagicMock)
def test_fetch_error_returns_error_verdict(mock_yf):
    mock_yf.Ticker.side_effect = RuntimeError("network error")

    result = fetch_options_liquidity([("BADTICKER", None, "lux")])
    assert result.iloc[0]["verdict"] == VERDICT_ERROR


def test_fetch_empty_input_returns_empty_df():
    result = fetch_options_liquidity([])
    assert result.empty


# --- filter_tradeable ---


def test_filter_tradeable_keeps_good_and_ok():
    df = pd.DataFrame(
        [
            {"symbol": "A", "verdict": VERDICT_GOOD, "total_oi": 10000},
            {"symbol": "B", "verdict": VERDICT_OK, "total_oi": 2000},
            {"symbol": "C", "verdict": VERDICT_ILLIQUID, "total_oi": 500},
            {"symbol": "D", "verdict": VERDICT_NO_OPTIONS, "total_oi": 0},
        ]
    )
    result = filter_tradeable(df)
    assert set(result["symbol"]) == {"A", "B"}


def test_filter_tradeable_sorts_good_before_ok():
    df = pd.DataFrame(
        [
            {"symbol": "B", "verdict": VERDICT_OK, "total_oi": 9000},
            {"symbol": "A", "verdict": VERDICT_GOOD, "total_oi": 1000},
        ]
    )
    result = filter_tradeable(df)
    assert result.iloc[0]["symbol"] == "A"


def test_filter_tradeable_empty_input():
    result = filter_tradeable(pd.DataFrame())
    assert result.empty

from types import SimpleNamespace

import pandas as pd

from stock_analyzer.main import render_analysis_report


def test_render_analysis_report_for_lux_is_concise():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.049988,
        trend="BULLISH",
        strength="NORMAL",
        adx=15.47,
        rsi=67.12,
        supertrend=263.22,
        upper_zone=276.10,
        lower_zone=251.33,
        confirmation_signal=0,
        contrarian_signal=0,
        combined_signal=0,
    )
    historical = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-04-18", "2026-04-19", "2026-04-20"]),
            "close": [270.23, 271.00, 273.05],
            "trend": ["BULLISH", "BULLISH", "BULLISH"],
            "adx": [14.98, 15.10, 15.47],
            "rsi": [65.10, 66.01, 67.12],
            "combined_signal": [0, 1, 0],
        }
    )

    report = render_analysis_report(
        symbol="AAPL",
        model="lux",
        signal=signal,
        historical=historical,
        recent_rows=2,
        signal_rows=2,
    )

    assert "Symbol: AAPL" in report
    assert "Interpretation" in report
    assert "bullish trend, normal strength, no active entry signal." in report
    assert "Current Snapshot" in report
    assert "Recent Rows (2)" in report
    assert "Recent Signal Events (1)" in report
    assert "2026-04-20" in report
    assert "BULLISH" in report
    assert "BUY" in report


def test_render_analysis_report_handles_no_signal_events():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.049988,
        rsi_value=45.0,
        sma_value=250.0,
        rsi_signal=0,
        sma_signal=0,
        combined_signal=0,
    )
    historical = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
            "close": [271.00, 273.05],
            "rsi": [44.2, 45.0],
            "sma": [249.5, 250.0],
            "combined_signal": [0, 0],
        }
    )

    report = render_analysis_report(
        symbol="AAPL",
        model="rsi-sma",
        signal=signal,
        historical=historical,
        recent_rows=2,
        signal_rows=2,
    )

    assert "RSI and SMA are not aligned, so the model remains on hold." in report
    assert "Recent Signal Events" in report
    assert "No non-HOLD events found." in report


def test_render_analysis_report_can_include_full_history():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.049988,
        rsi_value=45.0,
        sma_value=250.0,
        rsi_signal=0,
        sma_signal=0,
        combined_signal=0,
    )
    historical = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
            "close": [271.00, 273.05],
            "rsi": [44.2, 45.0],
            "sma": [249.5, 250.0],
            "combined_signal": [0, 0],
        }
    )

    report = render_analysis_report(
        symbol="AAPL",
        model="rsi-sma",
        signal=signal,
        historical=historical,
        full_history=True,
    )

    assert "Full History (2 rows)" in report

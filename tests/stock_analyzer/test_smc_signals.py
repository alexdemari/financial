from types import SimpleNamespace

import pandas as pd

from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.enums import Signal
from stock_analyzer.main import render_analysis_report
from stock_analyzer.signals import SMCSignalGenerator


def make_ohlc(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = pd.Series(
        [100 + i * 0.15 + ((i % 13) - 6) * 0.4 for i in range(rows)],
        index=index,
    )
    return pd.DataFrame(
        {
            "Open": close - 0.3,
            "High": close + 1.2,
            "Low": close - 1.1,
            "Close": close,
        },
        index=index,
    )


def test_smc_signal_generator_returns_historical_columns():
    generator = SMCSignalGenerator()

    result = generator.generate_historical_signals("AAPL", make_ohlc())

    expected_columns = {
        "date",
        "close",
        "combined_signal",
        "signal_bias",
        "signal_context",
        "rsi",
        "ema200",
        "range_position_pct",
        "in_premium",
        "in_discount",
        "bullish_rejection",
        "bearish_rejection",
        "bullish_divergence",
        "bearish_divergence",
        "long_signal",
        "short_signal",
    }
    assert expected_columns.issubset(result.columns)
    assert set(result["combined_signal"].dropna().unique()).issubset(
        {Signal.BUY, Signal.SELL, Signal.HOLD}
    )
    assert set(result["signal_bias"].unique()).issubset(
        {"BULLISH", "BEARISH", "NEUTRAL"}
    )


def test_smc_signal_generator_returns_current_signal():
    generator = SMCSignalGenerator()

    result = generator.generate_current_signal("AAPL", make_ohlc())

    assert result is not None
    assert result.symbol == "AAPL"
    assert result.combined_signal in {Signal.BUY, Signal.SELL, Signal.HOLD}
    assert result.bias in {"BULLISH", "BEARISH", "NEUTRAL"}


def test_stock_data_analyzer_can_select_smc_model():
    analyzer = StockDataAnalyzer(signal_model="smc")

    result = analyzer.generate_historical_signals("AAPL", make_ohlc())

    assert "signal_context" in result.columns
    assert "combined_signal" in result.columns


def test_render_analysis_report_for_smc_includes_context():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.05,
        bias="NEUTRAL",
        range_position_pct=62.5,
        rsi=54.3,
        ema200=250.0,
        in_premium=True,
        in_discount=False,
        bullish_rejection=False,
        bearish_rejection=True,
        bullish_divergence=False,
        bearish_divergence=False,
        long_signal=False,
        short_signal=False,
        combined_signal=0,
    )
    historical = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-04-18", "2026-04-19", "2026-04-20"]),
            "close": [270.23, 271.00, 273.05],
            "signal_bias": ["NEUTRAL", "NEUTRAL", "NEUTRAL"],
            "signal_context": ["no_trade", "premium_watch", "premium_watch"],
            "range_position_pct": [55.0, 60.0, 62.5],
            "rsi": [50.2, 52.0, 54.3],
            "combined_signal": [0, 0, 0],
        }
    )

    report = render_analysis_report(
        symbol="AAPL",
        model="smc",
        signal=signal,
        historical=historical,
        adapter=SMCSignalGenerator(),
        recent_rows=2,
        signal_rows=2,
    )

    assert "Symbol: AAPL" in report
    assert "Interpretation" in report
    assert "premium reversal watch." in report
    assert "Current Snapshot" in report
    assert "Range %" in report
    assert "Recent Rows (2)" in report
    assert "No non-HOLD events found." in report

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
        "options_hint",
        "rsi",
        "ema200",
        "range_position_pct",
        "swing_high_marker",
        "swing_low_marker",
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
    assert result.options_hint in {
        "CALL",
        "PUT",
        "CALL_WATCH",
        "PUT_WATCH",
        "NO_TRADE",
    }
    assert isinstance(result.swing_high_marker, bool)
    assert isinstance(result.swing_low_marker, bool)


def test_smc_signal_generator_uses_historical_rsi_series():
    generator = SMCSignalGenerator()

    result = generator.generate_historical_signals("AAPL", make_ohlc())

    recent_rsi = result["rsi"].tail(8)

    assert recent_rsi.nunique() > 1


def test_stock_data_analyzer_can_select_smc_model():
    analyzer = StockDataAnalyzer(signal_model="smc")

    result = analyzer.generate_historical_signals("AAPL", make_ohlc())

    assert "signal_context" in result.columns
    assert "combined_signal" in result.columns


def test_smc_signal_generator_marks_options_hint_for_structure_reversal():
    generator = SMCSignalGenerator()
    df = pd.DataFrame(
        {
            "Open": [10.0, 11.0, 12.0],
            "High": [11.0, 12.0, 13.0],
            "Low": [9.0, 10.0, 11.0],
            "Close": [10.5, 11.5, 12.5],
        },
        index=pd.to_datetime(["2026-04-18", "2026-04-19", "2026-04-20"]),
    )
    generator.indicator.compute = lambda prepared: SimpleNamespace(
        rsi=pd.Series([40.0, 52.0, 48.0], index=prepared.index),
        ema200=pd.Series([10.0, 10.5, 11.0], index=prepared.index),
        range_high=pd.Series([11.0, 12.0, 13.0], index=prepared.index),
        range_low=pd.Series([9.0, 10.0, 11.0], index=prepared.index),
        swing_highs=pd.Series([pd.NA, 12.0, pd.NA], index=prepared.index),
        swing_lows=pd.Series([9.0, pd.NA, pd.NA], index=prepared.index),
        in_premium=pd.Series([False, True, False], index=prepared.index),
        in_discount=pd.Series([True, False, True], index=prepared.index),
        bullish_rejection=pd.Series([False, False, False], index=prepared.index),
        bearish_rejection=pd.Series([False, False, False], index=prepared.index),
        bullish_divergence=pd.Series([False, False, False], index=prepared.index),
        bearish_divergence=pd.Series([False, False, False], index=prepared.index),
        long_signal=pd.Series([False, False, False], index=prepared.index),
        short_signal=pd.Series([False, False, False], index=prepared.index),
    )

    historical = generator.generate_historical_signals("AAPL", df)

    assert historical["options_hint"].tolist() == [
        "CALL_WATCH",
        "PUT_WATCH",
        "NO_TRADE",
    ]
    assert historical["signal_context"].tolist() == [
        "short_term_bullish_reversal",
        "short_term_bearish_reversal",
        "no_trade",
    ]


def test_render_analysis_report_for_smc_includes_context():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.05,
        bias="NEUTRAL",
        range_position_pct=62.5,
        rsi=54.3,
        ema200=250.0,
        options_hint="PUT_WATCH",
        swing_high_marker=True,
        swing_low_marker=False,
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
            "signal_context": [
                "no_trade",
                "premium_watch",
                "short_term_bearish_reversal",
            ],
            "options_hint": ["NO_TRADE", "PUT_WATCH", "PUT_WATCH"],
            "range_position_pct": [55.0, 60.0, 62.5],
            "rsi": [50.2, 52.0, 54.3],
            "swing_high_marker": [False, False, True],
            "swing_low_marker": [False, False, False],
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
    assert "Options Hint" in report
    assert "PUT_WATCH" in report
    assert "Swing High" in report
    assert "Recent Rows (2)" in report
    assert "Recent Structure Markers (1)" in report
    assert "No non-HOLD events found." in report


def test_render_analysis_report_for_smc_handles_missing_structure_markers():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.05,
        bias="NEUTRAL",
        range_position_pct=62.5,
        rsi=54.3,
        ema200=250.0,
        options_hint="NO_TRADE",
        swing_high_marker=False,
        swing_low_marker=False,
        in_premium=False,
        in_discount=True,
        bullish_rejection=False,
        bearish_rejection=False,
        bullish_divergence=False,
        bearish_divergence=False,
        long_signal=False,
        short_signal=False,
        combined_signal=0,
    )
    historical = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-04-19", "2026-04-20"]),
            "close": [271.00, 273.05],
            "signal_bias": ["NEUTRAL", "NEUTRAL"],
            "signal_context": ["no_trade", "no_trade"],
            "options_hint": ["NO_TRADE", "NO_TRADE"],
            "range_position_pct": [60.0, 62.5],
            "rsi": [52.0, 54.3],
            "swing_high_marker": [False, False],
            "swing_low_marker": [False, False],
            "combined_signal": [0, 0],
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

    assert "Recent Structure Markers" in report
    assert "No swing markers found." in report

from types import SimpleNamespace

import pandas as pd

from stock_analyzer.main import main, render_analysis_report
from stock_analyzer.signals import (
    LuxSignalGenerator,
    SignalGenerator,
    SMCSignalGenerator,
)


def test_render_analysis_report_for_lux_is_concise():
    signal = SimpleNamespace(
        date=pd.Timestamp("2026-04-20"),
        close_price=273.049988,
        trend="BULLISH",
        strength="NORMAL",
        options_hint="CALL",
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
            "signal_context": ["no_trade", "trend_confirmation_buy", "no_trade"],
            "options_hint": ["NO_TRADE", "CALL", "NO_TRADE"],
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
        adapter=LuxSignalGenerator(),
        recent_rows=2,
        signal_rows=2,
    )

    assert "Symbol: AAPL" in report
    assert "Interpretation" in report
    assert "bullish trend, normal strength, no active entry signal." in report
    assert "Current Snapshot" in report
    assert "Options Hint" in report
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
        adapter=SignalGenerator(),
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
        adapter=SignalGenerator(),
        full_history=True,
    )

    assert "Full History (2 rows)" in report


def test_main_accepts_smc_model(monkeypatch):
    calls = []
    df = pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-04-20"]))

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            calls.append(("init", signal_model))
            self.config = config
            self.signal_model = signal_model
            self.signal_generator = SMCSignalGenerator()

        def load_local_data(self, symbol, data_dir, interval):
            calls.append(("local", symbol, str(data_dir), interval))
            return df

        def retrieve_data(self, symbol, data_dir, interval):
            calls.append(("update", symbol, str(data_dir), interval))
            return df

        def generate_signal(self, symbol, data):
            return SimpleNamespace(
                date=pd.Timestamp("2026-04-20"),
                close_price=1.0,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
                ema200=1.0,
                options_hint="NO_TRADE",
                swing_high_marker=False,
                swing_low_marker=False,
                in_premium=False,
                in_discount=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bullish_divergence=False,
                bearish_divergence=False,
                long_signal=False,
                short_signal=False,
                combined_signal=0,
            )

        def generate_historical_signals(self, symbol, data):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-04-20"]),
                    "close": [1.0],
                    "signal_bias": ["NEUTRAL"],
                    "signal_context": ["no_trade"],
                    "range_position_pct": [50.0],
                    "rsi": [50.0],
                    "combined_signal": [0],
                }
            )

    monkeypatch.setattr("stock_analyzer.main.StockDataAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "stock_analyzer.main.render_analysis_report",
        lambda **kwargs: "REPORT",
    )

    exit_code = main(["-s", "AAPL", "--model", "smc", "--local-only"])

    assert exit_code == 0
    assert calls == [
        ("init", "smc"),
        ("local", "AAPL", str(data_dir()), "1d"),
    ]


def test_main_local_only_reads_local_csv(monkeypatch):
    calls = []
    df = pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-04-20"]))

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.config = config
            self.signal_model = signal_model
            self.signal_generator = SignalGenerator()
            self.signal_generator = LuxSignalGenerator()

        def load_local_data(self, symbol, data_dir, interval):
            calls.append(("local", symbol, str(data_dir), interval))
            return df

        def retrieve_data(self, symbol, data_dir, interval):
            calls.append(("update", symbol, str(data_dir), interval))
            return df

        def generate_signal(self, symbol, data):
            return SimpleNamespace(
                date=pd.Timestamp("2026-04-20"),
                close_price=1.0,
                trend="BULLISH",
                strength="NORMAL",
                options_hint="NO_TRADE",
                adx=20.0,
                rsi=55.0,
                supertrend=0.9,
                upper_zone=1.2,
                lower_zone=0.8,
                confirmation_signal=0,
                contrarian_signal=0,
                combined_signal=0,
            )

        def generate_historical_signals(self, symbol, data):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-04-20"]),
                    "close": [1.0],
                    "trend": ["BULLISH"],
                    "signal_context": ["no_trade"],
                    "options_hint": ["NO_TRADE"],
                    "adx": [20.0],
                    "rsi": [55.0],
                    "combined_signal": [0],
                }
            )

    monkeypatch.setattr("stock_analyzer.main.StockDataAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "stock_analyzer.main.render_analysis_report",
        lambda **kwargs: "REPORT",
    )

    exit_code = main(["-s", "AAPL", "--model", "lux", "--local-only"])

    assert exit_code == 0
    assert calls == [("local", "AAPL", str(data_dir()), "1d")]


def test_main_local_only_fails_without_csv(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.config = config
            self.signal_model = signal_model
            self.signal_generator = SignalGenerator()

        def load_local_data(self, symbol, data_dir, interval):
            raise FileNotFoundError("Local CSV not found")

    monkeypatch.setattr("stock_analyzer.main.StockDataAnalyzer", FakeAnalyzer)

    exit_code = main(["-s", "AAPL", "--local-only"])

    assert exit_code == 1


def test_main_default_mode_keeps_update_behavior(monkeypatch):
    calls = []
    df = pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-04-20"]))

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.config = config
            self.signal_model = signal_model
            self.signal_generator = SignalGenerator()

        def load_local_data(self, symbol, data_dir, interval):
            calls.append(("local", symbol, str(data_dir), interval))
            return df

        def retrieve_data(self, symbol, data_dir, interval):
            calls.append(("update", symbol, str(data_dir), interval))
            return df

        def generate_signal(self, symbol, data):
            return SimpleNamespace(
                date=pd.Timestamp("2026-04-20"),
                close_price=1.0,
                rsi_value=45.0,
                sma_value=1.0,
                rsi_signal=0,
                sma_signal=0,
                combined_signal=0,
            )

        def generate_historical_signals(self, symbol, data):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-04-20"]),
                    "close": [1.0],
                    "rsi": [45.0],
                    "sma": [1.0],
                    "combined_signal": [0],
                }
            )

    monkeypatch.setattr("stock_analyzer.main.StockDataAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "stock_analyzer.main.render_analysis_report",
        lambda **kwargs: "REPORT",
    )

    exit_code = main(["-s", "AAPL"])

    assert exit_code == 0
    assert calls == [("update", "AAPL", str(data_dir()), "1d")]


def data_dir():
    from stock_analyzer.main import DATA_DIR

    return DATA_DIR

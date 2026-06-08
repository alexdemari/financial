from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.decision import (
    TechnicalSignalResult,
    evaluate_asset,
    get_technical_signal,
)
from dividend_tracker.dividend_data import DividendData
from dividend_tracker.price_ceiling import PriceCeilingResult, calculate_price_ceiling
from stock_analyzer.enums import Signal


def _asset() -> DividendAssetConfig:
    return DividendAssetConfig(
        ticker="EGIE3",
        sector="Energia",
        name="Engie",
        target_weight=1.0,
        technical_model="smc",
        market="BR",
    )


def _ceiling(current_price: float, price_ceiling: float) -> PriceCeilingResult:
    return PriceCeilingResult(
        ticker="EGIE3",
        price_ceiling=price_ceiling,
        current_dy=0.06,
        trailing_annual_dividends=3.0,
        current_price=current_price,
        margin_pct=(price_ceiling - current_price) / current_price,
    )


def _technical(signal: str) -> TechnicalSignalResult:
    return TechnicalSignalResult(
        signal=signal,
        model="smc",
        event_type=signal,
        days_since_event=0,
        interpretation="mock",
    )


def test_decision_buy_when_price_ok_and_technical_buy():
    result = evaluate_asset(_asset(), _ceiling(40.0, 50.0), _technical("BUY"))

    assert result.decision == "BUY"


def test_decision_watch_when_price_ok_and_technical_watch():
    result = evaluate_asset(_asset(), _ceiling(40.0, 50.0), _technical("WATCH"))

    assert result.decision == "WATCH"


def test_decision_wait_when_price_ok_and_technical_wait():
    result = evaluate_asset(_asset(), _ceiling(40.0, 50.0), _technical("WAIT"))

    assert result.decision == "WAIT"


def test_decision_wait_when_price_ok_and_technical_neutral():
    result = evaluate_asset(_asset(), _ceiling(40.0, 50.0), _technical("NEUTRAL"))

    assert result.decision == "WAIT"


def test_decision_overpriced_for_any_technical_signal_when_above_ceiling():
    for technical_signal in ("BUY", "WATCH", "WAIT", "NEUTRAL"):
        result = evaluate_asset(
            _asset(),
            _ceiling(60.0, 50.0),
            _technical(technical_signal),
        )

        assert result.decision == "OVERPRICED"


def test_decision_uses_price_ceiling_calculated_with_custom_min_dy():
    asset = DividendAssetConfig(
        ticker="PEP",
        sector="Consumer Staples",
        name="PepsiCo",
        target_weight=0.0,
        technical_model="smc",
        market="US",
        min_dy=0.038,
    )
    dividend_data = DividendData(
        ticker="PEP",
        yahoo_ticker="PEP",
        current_price=140.68,
        trailing_annual_dividends=5.92,
        trailing_dy=0.0421,
        distributions=[],
        fetched_at=datetime.now(UTC),
    )

    assert asset.min_dy is not None
    custom_ceiling = calculate_price_ceiling(
        "PEP",
        min_dy=asset.min_dy,
        dividend_data=dividend_data,
    )
    global_ceiling = calculate_price_ceiling(
        "PEP",
        min_dy=0.06,
        dividend_data=dividend_data,
    )

    assert custom_ceiling.is_below_or_equal_ceiling is True
    assert global_ceiling.is_below_or_equal_ceiling is False
    assert evaluate_asset(asset, custom_ceiling, _technical("BUY")).decision == "BUY"


def test_get_technical_signal_maps_current_buy(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, signal_model):
            self.signal_model = signal_model
            self.signal_generator = SimpleNamespace(interpret=lambda signal: "buy")

        def load_local_data(self, symbol, data_dir, interval):
            assert symbol == "EGIE3.SA"
            assert str(data_dir) == "/tmp/stocks"
            assert interval == "1d"
            return pd.DataFrame({"Close": [1.0]})

        def generate_signal(self, symbol, ohlc_df):
            return SimpleNamespace(combined_signal=Signal.BUY)

        def generate_historical_signals(self, symbol, ohlc_df):
            return pd.DataFrame()

    monkeypatch.setattr("dividend_tracker.decision.StockDataAnalyzer", FakeAnalyzer)

    result = get_technical_signal(_asset(), data_dir="/tmp/stocks", local_only=True)

    assert result.signal == "BUY"
    assert result.model == "smc"
    assert result.event_type == "NONE"
    assert result.days_since_event is None


def test_get_technical_signal_maps_empty_history_to_neutral(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, signal_model):
            self.signal_generator = SimpleNamespace(interpret=lambda signal: "neutral")

        def load_local_data(self, symbol, data_dir, interval):
            return pd.DataFrame({"Close": [1.0]})

        def generate_signal(self, symbol, ohlc_df):
            return None

        def generate_historical_signals(self, symbol, ohlc_df):
            return pd.DataFrame()

    monkeypatch.setattr("dividend_tracker.decision.StockDataAnalyzer", FakeAnalyzer)

    result = get_technical_signal(_asset())

    assert result.signal == "NEUTRAL"
    assert result.event_type == "NONE"


def test_get_technical_signal_does_not_watch_on_sell_event_today(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, signal_model):
            self.signal_generator = SimpleNamespace(interpret=lambda signal: "neutral")

        def load_local_data(self, symbol, data_dir, interval):
            return pd.DataFrame({"Close": [1.0]})

        def generate_signal(self, symbol, ohlc_df):
            return None

        def generate_historical_signals(self, symbol, ohlc_df):
            return pd.DataFrame({"combined_signal": [Signal.SELL]})

    monkeypatch.setattr("dividend_tracker.decision.StockDataAnalyzer", FakeAnalyzer)

    result = get_technical_signal(_asset())

    assert result.signal == "NEUTRAL"
    assert result.event_type == "SELL"
    assert result.days_since_event == 0


def test_get_technical_signal_propagates_missing_local_csv(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, signal_model):
            self.signal_generator = SimpleNamespace(interpret=lambda signal: "missing")

        def load_local_data(self, symbol, data_dir, interval):
            raise FileNotFoundError("Local CSV not found")

    monkeypatch.setattr("dividend_tracker.decision.StockDataAnalyzer", FakeAnalyzer)

    with pytest.raises(FileNotFoundError, match="Local CSV not found"):
        get_technical_signal(_asset(), local_only=True)

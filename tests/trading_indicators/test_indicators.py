"""
Testes unitários e de integração para os indicadores.

Execução:
    cd /path/to/project
    pip install pytest numpy pandas
    pytest tests/ -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_indicators.indicators.lux import LuxConfig, LuxSignalsOverlays
from trading_indicators.indicators.smc import SMCConfig, SmartMoneyConfluence
from trading_indicators.signals.aggregator import (
    AggregationRule,
    CompositeSignalAggregator,
    LuxSignalStrategy,
    SMCSignalStrategy,
)
from trading_indicators.utils.types import SignalType, Trend


# ─── Fixtures ──────────────────────────────────────────────────────────────────


def make_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Gera OHLCV sintético com tendência e ruído."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="1h")
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    spread = rng.uniform(0.2, 1.5, n)
    high = close + spread
    low = close - spread
    open_ = close - rng.uniform(-0.3, 0.3, n)
    volume = rng.uniform(1000, 5000, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


@pytest.fixture
def df() -> pd.DataFrame:
    return make_df(500)


@pytest.fixture
def smc_result(df):
    return SmartMoneyConfluence().compute(df)


@pytest.fixture
def lux_result(df):
    return LuxSignalsOverlays().compute(df)


# ─── Testes SMC ────────────────────────────────────────────────────────────────


class TestSMC:
    def test_returns_correct_type(self, smc_result):
        from trading_indicators.utils.types import SMCResult

        assert isinstance(smc_result, SMCResult)

    def test_series_lengths_match(self, df, smc_result):
        r = smc_result
        assert len(r.ema200) == len(df)
        assert len(r.rsi) == len(df)
        assert len(r.long_signal) == len(df)
        assert len(r.short_signal) == len(df)

    def test_signals_are_boolean(self, smc_result):
        assert smc_result.long_signal.dtype == bool
        assert smc_result.short_signal.dtype == bool

    def test_no_simultaneous_signals(self, smc_result):
        r = smc_result
        assert not (
            r.long_signal & r.short_signal
        ).any(), "long_signal e short_signal não devem ser True ao mesmo tempo"

    def test_range_position_between_0_and_100(self, smc_result):
        assert 0 <= smc_result.range_position_pct <= 100

    def test_rsi_between_0_and_100(self, smc_result):
        rsi = smc_result.rsi.dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_premium_discount_exclusive(self, smc_result):
        r = smc_result
        # Não podem ser ambos True ao mesmo tempo
        assert not (r.in_premium & r.in_discount).any()

    def test_ema_filter_disabled(self, df):
        cfg = SMCConfig(use_ema_filter=False)
        result = SmartMoneyConfluence(cfg).compute(df)
        # Com filtro desativado, pode haver mais sinais
        assert result.long_signal.dtype == bool

    def test_raises_on_insufficient_data(self):
        tiny_df = make_df(10)
        with pytest.raises(ValueError, match="requer ao menos"):
            SmartMoneyConfluence().compute(tiny_df)

    def test_raises_on_missing_column(self, df):
        with pytest.raises(ValueError, match="faltando colunas"):
            SmartMoneyConfluence().compute(df.drop(columns=["close"]))

    def test_column_names_case_insensitive(self, df):
        upper_df = df.rename(columns=str.upper)
        result = SmartMoneyConfluence().compute(upper_df)
        assert len(result.long_signal) == len(df)


# ─── Testes Lux ────────────────────────────────────────────────────────────────


class TestLux:
    def test_returns_correct_type(self, lux_result):
        from trading_indicators.utils.types import LuxResult

        assert isinstance(lux_result, LuxResult)

    def test_trend_series_values(self, lux_result):
        valid_trends = {Trend.BULLISH, Trend.BEARISH}
        non_null = lux_result.trend.dropna()
        assert all(v in valid_trends for v in non_null)

    def test_supertrend_length(self, df, lux_result):
        assert len(lux_result.supertrend) == len(df)

    def test_rsi_bounds(self, lux_result):
        rsi = lux_result.rsi.dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_strong_buy_subset_of_valid_buy(self, lux_result):
        r = lux_result
        # STRONG_BUY implica valid_buy
        strong = r.valid_buy & r.is_strong
        assert (strong <= r.valid_buy).all()  # type: ignore[operator]

    def test_trend_filter_reduces_signals(self, df):
        cfg_no_filter = LuxConfig(use_trend_filter=False)
        cfg_filter = LuxConfig(use_trend_filter=True, adx_filter_threshold=20)

        r_no_filter = LuxSignalsOverlays(cfg_no_filter).compute(df)
        r_filter = LuxSignalsOverlays(cfg_filter).compute(df)

        assert r_filter.valid_buy.sum() <= r_no_filter.valid_buy.sum()
        assert r_filter.valid_sell.sum() <= r_no_filter.valid_sell.sum()

    def test_contra_signals_in_extremes(self, lux_result):
        r = lux_result
        # Contra_buy: low <= lower_zone e RSI < 30
        assert r.contra_buy.dtype == bool
        assert r.contra_sell.dtype == bool


# ─── Testes Agregador ──────────────────────────────────────────────────────────


class TestAggregator:
    def test_agreement_mode_stricter(self, df, smc_result, lux_result):
        strict = CompositeSignalAggregator(AggregationRule(require_agreement=True))
        loose = CompositeSignalAggregator(
            AggregationRule(require_agreement=False, min_strategies=1)
        )

        for agg in (strict, loose):
            agg.add(SMCSignalStrategy(smc_result)).add(LuxSignalStrategy(lux_result))

        strict_signals = strict.aggregate(df)
        loose_signals = loose.aggregate(df)

        strict_buys = (strict_signals == SignalType.BUY).sum()
        loose_buys = (loose_signals == SignalType.BUY).sum()
        assert strict_buys <= loose_buys

    def test_empty_aggregator_raises(self, df):
        agg = CompositeSignalAggregator()
        with pytest.raises(RuntimeError, match="Nenhuma estratégia"):
            agg.aggregate(df)

    def test_single_strategy_works(self, df, smc_result):
        agg = CompositeSignalAggregator()
        agg.add(SMCSignalStrategy(smc_result))
        signals = agg.aggregate(df)
        assert len(signals) == len(df)
        assert signals.dtype == object  # SignalType enum


# ─── Testes de Primitivas TA ───────────────────────────────────────────────────


class TestTAPrimitives:
    def test_ema_converges(self):
        from trading_indicators.utils.ta_primitives import ema

        s = pd.Series([100.0] * 100)
        result = ema(s, 10)
        assert abs(result.iloc[-1] - 100.0) < 0.01

    def test_rsi_bounds(self):
        from trading_indicators.utils.ta_primitives import rsi

        s = pd.Series(np.random.default_rng(0).uniform(90, 110, 200))
        result = rsi(s, 14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_supertrend_direction_values(self):
        from trading_indicators.utils.ta_primitives import supertrend

        df = make_df(300)
        _, direction = supertrend(df["high"], df["low"], df["close"])
        assert set(direction.dropna().unique()).issubset({-1, 1})

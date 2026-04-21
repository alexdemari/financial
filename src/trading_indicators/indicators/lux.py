"""
Signals & Overlays — Lux Replica
Port do indicador Pine Script para Python.

Combina:
  - Supertrend (Smart Trail)
  - Bandas de reversão (Bollinger-style)
  - ADX para filtragem de força
  - Sinais de confirmação e contrarian (RSI + Bandas)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trading_indicators.indicators.base import BaseIndicator
from trading_indicators.utils import ta_primitives as ta
from trading_indicators.utils.types import LuxResult, Trend


@dataclass
class LuxConfig:
    """Parâmetros configuráveis do indicador Lux."""

    sensitivity: int = 14  # Período do Supertrend / ATR
    multiplier: float = 1.5  # Multiplicador do Supertrend
    use_trend_filter: bool = False  # Aplicar filtro ADX nos sinais de confirmação
    adx_filter_threshold: float = 20.0  # ADX mínimo quando filtro ativo
    adx_strong_threshold: float = 25.0  # ADX mínimo para sinal "forte"
    bollinger_length: int = 20  # Janela das bandas de reversão
    bollinger_mult: float = 2.0  # Multiplicador do desvio das bandas
    rsi_length: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0


class LuxSignalsOverlays(BaseIndicator[LuxResult]):
    """
    Indicador Lux Signals & Overlays.

    Exemplo de uso::

        from trading_indicators.indicators.lux import LuxSignalsOverlays, LuxConfig

        config = LuxConfig(sensitivity=14, multiplier=1.5, use_trend_filter=True)
        lux = LuxSignalsOverlays(config)
        result = lux.compute(df)

        # Candles com compra forte confirmada
        strong_buys = df[result.valid_buy & result.is_strong]
    """

    def __init__(self, config: LuxConfig | None = None) -> None:
        self.config = config or LuxConfig()

    def _min_bars(self) -> int:
        cfg = self.config
        return max(200, cfg.sensitivity * 2, cfg.bollinger_length * 2)

    def _compute(self, df: pd.DataFrame) -> LuxResult:
        cfg = self.config
        close = df["close"]
        high = df["high"]
        low = df["low"]

        # ── Supertrend (Smart Trail) ──────────────────────────────────────────
        st_line, direction = ta.supertrend(
            high, low, close, cfg.multiplier, cfg.sensitivity
        )

        trend = direction.map({-1: Trend.BULLISH, 1: Trend.BEARISH})  # type: ignore[arg-type]
        # ── Bandas de Reversão ────────────────────────────────────────────────
        basis = ta.sma(close, cfg.bollinger_length)
        dev = cfg.bollinger_mult * ta.stdev(close, cfg.bollinger_length)
        upper_zone = basis + dev
        lower_zone = basis - dev

        # ── ADX / Força ───────────────────────────────────────────────────────
        _, _, adx_val = ta.dmi(high, low, close, di_length=14, adx_length=14)
        is_strong = adx_val > cfg.adx_strong_threshold

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_val = ta.rsi(close, cfg.rsi_length)

        # ── Sinais de Confirmação ─────────────────────────────────────────────
        signal_buy = _crossover(close, st_line)
        signal_sell = _crossunder(close, st_line)

        if cfg.use_trend_filter:
            valid_buy = signal_buy & (adx_val > cfg.adx_filter_threshold)
            valid_sell = signal_sell & (adx_val > cfg.adx_filter_threshold)
        else:
            valid_buy = signal_buy.copy()
            valid_sell = signal_sell.copy()

        # ── Sinais Contrarian ─────────────────────────────────────────────────
        contra_buy = (low <= lower_zone) & (rsi_val < cfg.rsi_oversold)
        contra_sell = (high >= upper_zone) & (rsi_val > cfg.rsi_overbought)

        return LuxResult(
            supertrend=st_line,
            trend=trend,
            upper_zone=upper_zone,
            lower_zone=lower_zone,
            basis=basis,
            adx=adx_val,
            is_strong=is_strong,
            signal_buy=signal_buy,
            signal_sell=signal_sell,
            valid_buy=valid_buy,
            valid_sell=valid_sell,
            contra_buy=contra_buy,
            contra_sell=contra_sell,
            rsi=rsi_val,
        )


# ─── Helpers locais ────────────────────────────────────────────────────────────


def _crossover(series: pd.Series, reference: pd.Series) -> pd.Series:
    """True quando series cruza reference de baixo para cima."""
    return (series > reference) & (series.shift(1) <= reference.shift(1))


def _crossunder(series: pd.Series, reference: pd.Series) -> pd.Series:
    """True quando series cruza reference de cima para baixo."""
    return (series < reference) & (series.shift(1) >= reference.shift(1))

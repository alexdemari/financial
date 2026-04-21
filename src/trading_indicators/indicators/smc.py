"""
Smart Money Confluence — Pro Edition
Port do indicador Pine Script para Python.

Detecta confluência entre:
  - Divergência RSI
  - Rejeição de pavio (wick rejection)
  - Zona Premium/Discount
  - Filtro de tendência EMA 200 (opcional)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_indicators.indicators.base import BaseIndicator
from trading_indicators.utils import ta_primitives as ta
from trading_indicators.utils.types import SMCResult


@dataclass
class SMCConfig:
    """Parâmetros configuráveis do indicador SMC."""

    swing_lookback: int = 10
    wick_threshold: float = 0.6  # Proporção mínima do pavio no range total
    range_lookback: int = 50  # Janela para cálculo de Premium/Discount
    rsi_length: int = 14
    divergence_lookback: int = 20
    use_ema_filter: bool = True


class SmartMoneyConfluence(BaseIndicator[SMCResult]):
    """
    Indicador Smart Money Confluence.

    Exemplo de uso::

        from trading_indicators.indicators.smc import SmartMoneyConfluence, SMCConfig

        config = SMCConfig(swing_lookback=10, use_ema_filter=True)
        smc = SmartMoneyConfluence(config)
        result = smc.compute(df)

        # Filtrar apenas barras com sinal de compra
        buy_bars = df[result.long_signal]
    """

    def __init__(self, config: SMCConfig | None = None) -> None:
        self.config = config or SMCConfig()

    def _min_bars(self) -> int:
        cfg = self.config
        return max(
            200, cfg.range_lookback, cfg.divergence_lookback, cfg.swing_lookback * 2 + 1
        )

    def _compute(self, df: pd.DataFrame) -> SMCResult:
        cfg = self.config
        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_ = df["open"]

        # ── EMA 200 ──────────────────────────────────────────────────────────
        ema200 = ta.ema(close, 200)

        # ── Pivôs ─────────────────────────────────────────────────────────────
        swing_highs = ta.pivot_high(high, cfg.swing_lookback, cfg.swing_lookback)
        swing_lows = ta.pivot_low(low, cfg.swing_lookback, cfg.swing_lookback)

        # ── Rejeição de Pavio ─────────────────────────────────────────────────
        total_range = high - low
        upper_wick = high - pd.concat([close, open_], axis=1).max(axis=1)
        lower_wick = pd.concat([close, open_], axis=1).min(axis=1) - low

        safe_range = total_range.replace(0, np.nan)
        bearish_rejection = (upper_wick / safe_range) >= cfg.wick_threshold
        bullish_rejection = (lower_wick / safe_range) >= cfg.wick_threshold

        # ── Premium / Discount ────────────────────────────────────────────────
        range_high = high.rolling(cfg.range_lookback).max()
        range_low = low.rolling(cfg.range_lookback).min()
        range_mid = (range_high + range_low) / 2

        in_premium = close > range_mid
        in_discount = close < range_mid

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_val = ta.rsi(close, cfg.rsi_length)

        # ── Divergência RSI ───────────────────────────────────────────────────
        # Bearish: Preço faz topo maior, RSI faz topo menor (zona Premium)
        prev_high_max = high.rolling(cfg.divergence_lookback).max().shift(1)
        prev_rsi_max = rsi_val.rolling(cfg.divergence_lookback).max().shift(1)
        bearish_div = (high > prev_high_max) & (rsi_val < prev_rsi_max) & (rsi_val > 50)

        # Bullish: Preço faz fundo menor, RSI faz fundo maior (zona Discount)
        prev_low_min = low.rolling(cfg.divergence_lookback).min().shift(1)
        prev_rsi_min = rsi_val.rolling(cfg.divergence_lookback).min().shift(1)
        bullish_div = (low < prev_low_min) & (rsi_val > prev_rsi_min) & (rsi_val < 50)

        # ── Sinais Finais ─────────────────────────────────────────────────────
        ema_long_ok = (
            (close > ema200)
            if cfg.use_ema_filter
            else pd.Series(True, index=close.index)
        )
        ema_short_ok = (
            (close < ema200)
            if cfg.use_ema_filter
            else pd.Series(True, index=close.index)
        )

        long_signal = bullish_div & bullish_rejection & in_discount & ema_long_ok
        short_signal = bearish_div & bearish_rejection & in_premium & ema_short_ok

        # ── Métricas da Última Barra ──────────────────────────────────────────
        last_range_high = range_high.iloc[-1]
        last_range_low = range_low.iloc[-1]
        last_close = close.iloc[-1]
        span = last_range_high - last_range_low
        range_position_pct = (
            ((last_close - last_range_low) / span * 100) if span != 0 else 50.0
        )

        return SMCResult(
            ema200=ema200,
            range_high=range_high,
            range_low=range_low,
            range_mid=range_mid,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            bullish_rejection=bullish_rejection,
            bearish_rejection=bearish_rejection,
            in_premium=in_premium,
            in_discount=in_discount,
            bullish_divergence=bullish_div,
            bearish_divergence=bearish_div,
            long_signal=long_signal,
            short_signal=short_signal,
            range_position_pct=float(range_position_pct),
            rsi=float(rsi_val.iloc[-1]),
        )

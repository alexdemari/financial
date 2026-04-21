"""
Tipos e estruturas de dados compartilhados pelos indicadores.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import pandas as pd


class Trend(Enum):
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()


class SignalType(Enum):
    BUY = auto()
    STRONG_BUY = auto()
    SELL = auto()
    STRONG_SELL = auto()
    CONTRA_BUY = auto()
    CONTRA_SELL = auto()
    NONE = auto()


class ZonePosition(Enum):
    PREMIUM = auto()  # Acima do equilíbrio
    DISCOUNT = auto()  # Abaixo do equilíbrio
    EQUILIBRIUM = auto()


@dataclass(frozen=True)
class OHLCV:
    """Representa uma barra de preço."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @classmethod
    def from_series(cls, row: pd.Series) -> "OHLCV":
        return cls(
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
        )


@dataclass
class SMCResult:
    """Resultado completo do indicador Smart Money Confluence."""

    # Séries de preços (indexadas como o DataFrame original)
    ema200: pd.Series
    range_high: pd.Series
    range_low: pd.Series
    range_mid: pd.Series

    # Pivôs (valor presente apenas no candle do pivô, NaN nos demais)
    swing_highs: pd.Series
    swing_lows: pd.Series

    # Flags booleanas por candle
    bullish_rejection: pd.Series
    bearish_rejection: pd.Series
    in_premium: pd.Series
    in_discount: pd.Series
    bullish_divergence: pd.Series
    bearish_divergence: pd.Series

    # Sinais finais
    long_signal: pd.Series
    short_signal: pd.Series

    # Métricas escalares (última barra)
    range_position_pct: float
    rsi: float


@dataclass
class LuxResult:
    """Resultado completo do indicador Lux Signals & Overlays."""

    # Supertrend
    supertrend: pd.Series
    trend: pd.Series  # Série de Trend enum

    # Bandas de reversão
    upper_zone: pd.Series
    lower_zone: pd.Series
    basis: pd.Series

    # ADX / Força
    adx: pd.Series
    is_strong: pd.Series  # bool: ADX > 25

    # Sinais
    signal_buy: pd.Series  # Confirmação
    signal_sell: pd.Series
    valid_buy: pd.Series  # Com filtro opcional
    valid_sell: pd.Series
    contra_buy: pd.Series  # Contrarians
    contra_sell: pd.Series

    # RSI
    rsi: pd.Series

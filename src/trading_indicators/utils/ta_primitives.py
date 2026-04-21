"""
Primitivas de análise técnica reutilizáveis.

Todas as funções recebem e retornam pd.Series para manter consistência
com índices e facilitar composição.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ─── Médias ────────────────────────────────────────────────────────────────────


def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=length).mean()


def stdev(series: pd.Series, length: int) -> pd.Series:
    """Desvio padrão amostral com janela deslizante."""
    return series.rolling(window=length).std(ddof=0)


# ─── Osciladores ───────────────────────────────────────────────────────────────


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """
    RSI — Relative Strength Index.
    Implementação via Wilder (EMA com alpha = 1/length).
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def dmi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    di_length: int = 14,
    adx_length: int = 14,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Directional Movement Index.

    Returns:
        (DI+, DI-, ADX)
    """
    tr = _true_range(high, low, close)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    atr = _wilder_smooth(tr, di_length)
    di_plus = 100 * _wilder_smooth(plus_dm, di_length) / atr.replace(0, np.nan)
    di_minus = 100 * _wilder_smooth(minus_dm, di_length) / atr.replace(0, np.nan)

    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    adx_val = _wilder_smooth(dx, adx_length)

    return di_plus, di_minus, adx_val


# ─── Supertrend ────────────────────────────────────────────────────────────────


def supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    multiplier: float = 3.0,
    length: int = 10,
) -> tuple[pd.Series, pd.Series]:
    """
    Supertrend.

    Returns:
        (supertrend_line, direction)  — direction: -1 bullish, +1 bearish
    """
    hl2 = (high + low) / 2
    tr = _true_range(high, low, close)
    atr = tr.ewm(span=length, adjust=False).mean()

    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    st = pd.Series(np.nan, index=close.index)
    direction = pd.Series(1, index=close.index)

    for i in range(1, len(close)):
        prev_dir = direction.iloc[i - 1]
        prev_close = close.iloc[i - 1]
        curr_close = close.iloc[i]
        curr_upper = upper_band.iloc[i]
        curr_lower = lower_band.iloc[i]

        # Ajuste de bandas
        final_upper = (
            curr_upper
            if (
                curr_upper < upper_band.iloc[i - 1]
                or prev_close > upper_band.iloc[i - 1]
            )
            else upper_band.iloc[i - 1]
        )
        final_lower = (
            curr_lower
            if (
                curr_lower > lower_band.iloc[i - 1]
                or prev_close < lower_band.iloc[i - 1]
            )
            else lower_band.iloc[i - 1]
        )

        upper_band.iloc[i] = final_upper
        lower_band.iloc[i] = final_lower

        if prev_dir == 1 and curr_close > final_upper:
            direction.iloc[i] = -1
        elif prev_dir == -1 and curr_close < final_lower:
            direction.iloc[i] = 1
        else:
            direction.iloc[i] = prev_dir

        st.iloc[i] = final_lower if direction.iloc[i] == -1 else final_upper

    return st, direction


# ─── Pivôs ─────────────────────────────────────────────────────────────────────


def pivot_high(high: pd.Series, left_bars: int, right_bars: int) -> pd.Series:
    """
    Detecta topos de pivô.
    Retorna o valor do topo no índice do candle central; NaN nos demais.
    Semanticamente equivalente a ta.pivothigh() do Pine Script.
    """
    result = pd.Series(np.nan, index=high.index)
    n = len(high)
    for i in range(left_bars, n - right_bars):
        window = high.iloc[i - left_bars : i + right_bars + 1]
        pivot_val = high.iloc[i]
        if pivot_val == window.max():
            # Emite no índice deslocado (como Pine faz com offset=-swingLen)
            result.iloc[i] = pivot_val

    return result


def pivot_low(low: pd.Series, left_bars: int, right_bars: int) -> pd.Series:
    """Detecta fundos de pivô."""
    result = pd.Series(np.nan, index=low.index)
    n = len(low)

    for i in range(left_bars, n - right_bars):
        window = low.iloc[i - left_bars : i + right_bars + 1]
        pivot_val = low.iloc[i]
        if pivot_val == window.min():
            result.iloc[i] = pivot_val

    return result


# ─── Helpers privados ──────────────────────────────────────────────────────────


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _wilder_smooth(series: pd.Series, length: int) -> pd.Series:
    """Wilder smoothing (EMA com alpha=1/length)."""
    return series.ewm(alpha=1 / length, adjust=False).mean()

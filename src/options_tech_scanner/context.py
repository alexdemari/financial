# src/options_tech_scanner/context.py

import numpy as np
import pandas as pd


def historical_volatility(close: pd.Series, window: int = 30) -> float:
    """
    Volatilidade histórica anualizada (HV).
    """
    returns = close.pct_change().dropna()
    if len(returns) < window:
        return np.nan

    hv = returns.tail(window).std() * np.sqrt(252)
    return hv * 100  # %


def trend_sma200(close: pd.Series) -> float:
    """
    Distância percentual do preço para a SMA200.
    """
    sma200 = close.rolling(200).mean()
    if np.isnan(sma200.iloc[-1]):
        return np.nan

    return ((close.iloc[-1] / sma200.iloc[-1]) - 1) * 100


def order_block_support(low: pd.Series, lookback: int = 120) -> float:
    """
    Proxy simples de Order Block:
    mínima relevante recente (zona institucional).
    """
    if len(low) < lookback:
        return np.nan

    return low.tail(lookback).min()


def fair_value_gap(high: pd.Series, low: pd.Series) -> dict | None:
    """
    Detecção simples de Fair Value Gap (FVG).
    Retorna zona se existir, senão None.
    """
    if len(high) < 3:
        return None

    h2, h1 = high.iloc[-3], high.iloc[-2]
    l1, l0 = low.iloc[-2], low.iloc[-1]

    # FVG de alta
    if l1 > h2:
        return {
            "type": "BULLISH",
            "zone": (h2, l1)
        }

    # FVG de baixa
    if h1 < l0:
        return {
            "type": "BEARISH",
            "zone": (h1, l0)
        }

    return None


def compute_context(df: pd.DataFrame) -> dict:
    """
    Consolida métricas de contexto do ativo.
    """
    close = df["Close"]
    low = df["Low"]
    high = df["High"]

    return {
        "hv30": historical_volatility(close, 30),
        "trend_sma200_pct": trend_sma200(close),
        "order_block": order_block_support(low),
        "fvg": fair_value_gap(high, low),
    }

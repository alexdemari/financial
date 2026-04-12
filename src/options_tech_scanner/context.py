# src/options_tech_scanner/context.py

import numpy as np
import pandas as pd

from options_tech_scanner.indicators import ema_cloud, sma


def historical_volatility(close: pd.Series, window: int = 30) -> float:
    """
    Volatilidade histórica anualizada (HV).
    """
    returns = close.pct_change(fill_method=None).dropna()
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


def above_sma200(close: pd.Series) -> bool:
    sma200 = sma(close, 200)
    if np.isnan(sma200.iloc[-1]):
        return False
    return bool(close.iloc[-1] > sma200.iloc[-1])


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
        return {"type": "BULLISH", "zone": (h2, l1)}

    # FVG de baixa
    if h1 < l0:
        return {"type": "BEARISH", "zone": (h1, l0)}

    return None


def relative_strength_ratio(
    symbol_close: pd.Series, benchmark_close: pd.Series, lookback: int = 63
) -> float:
    aligned = pd.DataFrame(
        {"symbol": symbol_close, "benchmark": benchmark_close}
    ).dropna()
    if len(aligned) < lookback + 1:
        return np.nan

    tail = aligned.tail(lookback + 1)
    sym_ret = (tail["symbol"].iloc[-1] / tail["symbol"].iloc[0]) - 1
    bench_ret = (tail["benchmark"].iloc[-1] / tail["benchmark"].iloc[0]) - 1

    if np.isclose(1 + bench_ret, 0):
        return np.nan

    return (1 + sym_ret) / (1 + bench_ret)


def compute_context(
    df: pd.DataFrame,
    spy_df: pd.DataFrame | None = None,
    xlu_df: pd.DataFrame | None = None,
    rs_lookback: int = 63,
    indicator_frame: pd.DataFrame | None = None,
) -> dict:
    """
    Consolida métricas de contexto do ativo.
    """
    close = df["Close"]
    low = df["Low"]
    high = df["High"]
    if (
        indicator_frame is not None
        and {"EMA8", "EMA21", "CLOUD_GREEN"}.issubset(indicator_frame.columns)
        and len(indicator_frame) == len(df)
    ):
        ema8 = indicator_frame["EMA8"]
        ema21 = indicator_frame["EMA21"]
        cloud_green = indicator_frame["CLOUD_GREEN"]
    else:
        ema8, ema21, cloud_green = ema_cloud(close, 8, 21)

    rs_spy = (
        relative_strength_ratio(close, spy_df["Close"], rs_lookback)
        if spy_df is not None and "Close" in spy_df.columns
        else np.nan
    )
    rs_xlu = (
        relative_strength_ratio(close, xlu_df["Close"], rs_lookback)
        if xlu_df is not None and "Close" in xlu_df.columns
        else np.nan
    )

    alpha_rotation = bool(
        (not pd.isna(rs_spy) and rs_spy > 1) and (not pd.isna(rs_xlu) and rs_xlu > 1)
    )

    return {
        "hv30": historical_volatility(close, 30),
        "trend_sma200_pct": trend_sma200(close),
        "above_sma200": above_sma200(close),
        "ema8": float(ema8.iloc[-1]) if not pd.isna(ema8.iloc[-1]) else np.nan,
        "ema21": float(ema21.iloc[-1]) if not pd.isna(ema21.iloc[-1]) else np.nan,
        "ema_cloud_green": (
            bool(cloud_green.iloc[-1]) if not pd.isna(cloud_green.iloc[-1]) else False
        ),
        "rs_spy": rs_spy,
        "rs_xlu": rs_xlu,
        "alpha_rotation": alpha_rotation,
        "order_block": order_block_support(low),
        "fvg": fair_value_gap(high, low),
    }

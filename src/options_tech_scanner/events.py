from typing import List, Dict

import numpy as np
import pandas as pd

from options_tech_scanner.indicators import atr, rsi, sma
from options_tech_scanner.setups import classify_put_strategy


def detect_setups(
    df: pd.DataFrame,
    lookahead: int = 30,
    support_lookback: int = 60,
    mode: str = "core"
) -> List[Dict]:
    """
    Backtest técnico eficiente (O(N)) para CSP e Bull Put Spread.

    WIN definition:
    - CSP: Close final >= suporte
    - BULL_PUT_SPREAD: Close final >= suporte - 0.5 * ATR
    """

    events: List[Dict] = []

    min_bars = max(250, support_lookback) + lookahead
    if len(df) < min_bars:
        return events

    # =========================
    # Pré-cálculo (1x por ativo)
    # =========================

    close = df["Close"]
    low = df["Low"]

    atr_series = atr(df)
    rsi_series = rsi(close)

    # Suporte simples e rápido (rolling min)
    support_series = low.rolling(support_lookback).min()

    # Tendência (regime bullish) por candle
    sma200 = sma(close, 200)
    sma200_slope = sma200.diff(20)
    bullish_series = (close > sma200) & (sma200_slope > 0)

    # Proxy simples de volatilidade relativa
    atr_mean_252 = atr_series.rolling(252).mean()
    vol_ratio_series = atr_series / atr_mean_252

    # =========================
    # Loop O(N)
    # =========================

    for i in range(min_bars, len(df) - lookahead):

        atr_val = atr_series.iloc[i]
        support = support_series.iloc[i]

        if np.isnan(atr_val) or np.isnan(support) or atr_val == 0:
            continue

        dist_atr = (close.iloc[i] - support) / atr_val

        strategy = classify_put_strategy(
            bullish=bool(bullish_series.iloc[i]),
            rsi_val=rsi_series.iloc[i],
            dist_atr=dist_atr,
            vol_ratio=vol_ratio_series.iloc[i],
            mode=mode
        )

        if strategy is None:
            continue

        final_close = close.iloc[i + lookahead]

        # =========================
        # Regra de WIN
        # =========================

        if strategy == "CSP":
            win = final_close >= support

        else:  # BULL_PUT_SPREAD
            win = final_close >= (support - 0.5 * atr_val)

        events.append(
            {
                "date": df.index[i],
                "strategy": strategy,
                "rsi": rsi_series.iloc[i],
                "distance_to_support_atr": dist_atr,
                "volatility_ratio": vol_ratio_series.iloc[i],
                "win": win,
            }
        )

    return events

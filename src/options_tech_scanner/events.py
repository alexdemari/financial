from typing import Dict, List

import numpy as np
import pandas as pd

from options_tech_scanner.context import compute_context
from options_tech_scanner.indicators import atr, compute_indicator_frame
from options_tech_scanner.setups import evaluate_put_setup


def _benchmark_until_date(
    benchmark_df: pd.DataFrame | None, current_date: pd.Timestamp
) -> pd.DataFrame | None:
    if benchmark_df is None:
        return None
    return benchmark_df.loc[:current_date]


def detect_setups(
    df: pd.DataFrame,
    lookahead: int = 30,
    support_lookback: int = 60,
    mode: str = "core",
    spy_df: pd.DataFrame | None = None,
    xlu_df: pd.DataFrame | None = None,
    diagnostics: dict | None = None,
) -> List[Dict]:
    """
    Backtest técnico eficiente (O(N)) para CSP e Bull Put Spread.

    WIN definition:
    - CSP: Close final >= suporte
    - BULL_PUT_SPREAD: Close final >= suporte - 0.5 * ATR
    """

    events: List[Dict] = []

    min_bars = max(300, support_lookback) + lookahead
    if len(df) < min_bars:
        return events

    df = df.sort_index()
    close = df["Close"]
    low = df["Low"]
    indicator_full = compute_indicator_frame(df)
    atr_series = atr(df)
    support_series = low.rolling(support_lookback).min()

    for i in range(min_bars, len(df) - lookahead):
        current_date = df.index[i]
        hist_df = df.iloc[: i + 1]
        indicator_hist = indicator_full.iloc[: i + 1]

        spy_hist = _benchmark_until_date(spy_df, current_date)
        xlu_hist = _benchmark_until_date(xlu_df, current_date)
        context = compute_context(
            hist_df, spy_df=spy_hist, xlu_df=xlu_hist, indicator_frame=indicator_hist
        )

        setup = evaluate_put_setup(
            hist_df, mode=mode, context=context, indicator_frame=indicator_hist
        )

        if diagnostics is not None:
            diagnostics["bars_evaluated"] += 1
            diagnostics["pass_above_sma200"] += int(setup.get("above_sma200", False))
            diagnostics["pass_ema_cloud_green"] += int(
                setup.get("ema_cloud_green", False)
            )
            diagnostics["pass_rsi_pullback"] += int(setup.get("rsi_pullback_ok", False))
            diagnostics["pass_not_no_trade_zone"] += int(
                not setup.get("no_trade_zone", False)
            )
            diagnostics["pass_near_ema21"] += int(setup.get("near_ema21_ok", False))
            diagnostics["pass_price_action"] += int(setup.get("price_action_ok", False))
            diagnostics["pass_volume"] += int(setup.get("volume_ok", False))
            diagnostics["pass_alpha_rotation"] += int(
                setup.get("alpha_rotation", False)
            )

        strategy = setup.get("strategy")
        if strategy is None:
            continue

        if diagnostics is not None:
            diagnostics["final_setups"] += 1
            if strategy == "BULL_PUT_SPREAD":
                diagnostics["final_bps"] += 1
            elif strategy == "CSP":
                diagnostics["final_csp"] += 1

        atr_val = atr_series.iloc[i]
        support = support_series.iloc[i]
        if np.isnan(atr_val) or np.isnan(support) or atr_val == 0:
            continue

        entry_close = close.iloc[i]
        final_close = close.iloc[i + lookahead]

        if strategy == "CSP":
            win = final_close >= support
        else:  # BULL_PUT_SPREAD
            win = final_close >= (support - 0.5 * atr_val)

        events.append(
            {
                "date": current_date,
                "strategy": strategy,
                "entry_close": entry_close,
                "final_close": final_close,
                "rsi": setup.get("rsi"),
                "distance_to_support_atr": (entry_close - support) / atr_val,
                "distance_to_ema21_atr": setup.get("dist_ema21_atr"),
                "volatility_ratio": setup.get("vol_ratio"),
                "above_sma200": setup.get("above_sma200"),
                "ema_cloud_green": setup.get("ema_cloud_green"),
                "rsi_pullback_ok": setup.get("rsi_pullback_ok"),
                "no_trade_zone": setup.get("no_trade_zone"),
                "price_action_signal": setup.get("price_action_signal"),
                "price_action_ok": setup.get("price_action_ok"),
                "volume_ok": setup.get("volume_ok"),
                "alpha_rotation": setup.get("alpha_rotation"),
                "win": win,
            }
        )

    return events

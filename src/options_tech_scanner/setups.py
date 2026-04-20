import numpy as np
import pandas as pd

from options_tech_scanner.indicators import (
    atr,
    ema_cloud,
    is_bullish_engulfing,
    is_bullish_pin_bar,
    rsi,
    sma,
    volume_ratio,
)


def _legacy_classify(
    *,
    bullish: bool,
    rsi_val: float,
    dist_atr: float,
    vol_ratio: float,
    mode: str = "core",
) -> str | None:
    if mode == "core":
        min_dist = 0.8
    elif mode == "relaxed":
        min_dist = 0.45
    else:
        raise ValueError("mode invalido")

    if (
        bullish
        and min_dist <= dist_atr < 3.5
        and vol_ratio < 1.0
        and 35 <= rsi_val <= 60
    ):
        return "CSP"

    if min_dist <= dist_atr < 1.2 and vol_ratio < 1.5 and 40 <= rsi_val <= 65:
        return "BULL_PUT_SPREAD"

    return None


def evaluate_put_setup(
    df: pd.DataFrame,
    *,
    mode: str = "core",
    context: dict | None = None,
    indicator_frame: pd.DataFrame | None = None,
) -> dict:
    if df.empty or len(df) < 220:
        return {"strategy": None, "reason": "insufficient_data"}

    if mode == "core":
        near_ema21_max_atr = 0.6
        min_volume_ratio = 1.5
        price_action_lookback = 1
    elif mode == "relaxed":
        near_ema21_max_atr = 0.9
        min_volume_ratio = 1.2
        price_action_lookback = 3
    else:
        raise ValueError("mode invalido")

    close = df["Close"]
    if (
        indicator_frame is not None
        and {
            "SMA200",
            "EMA8",
            "EMA21",
            "CLOUD_GREEN",
            "RSI14",
            "ATR14",
            "VOL_RATIO20",
        }.issubset(indicator_frame.columns)
        and len(indicator_frame) == len(df)
    ):
        sma200 = indicator_frame["SMA200"]
        ema8 = indicator_frame["EMA8"]
        ema21 = indicator_frame["EMA21"]
        cloud_green = indicator_frame["CLOUD_GREEN"]
        rsi_series = indicator_frame["RSI14"]
        atr_series = indicator_frame["ATR14"]
        vol_ratio_series = indicator_frame["VOL_RATIO20"]
    else:
        sma200 = sma(close, 200)
        ema8, ema21, cloud_green = ema_cloud(close, 8, 21)
        rsi_series = rsi(close, 14)
        atr_series = atr(df, 14)
        vol_ratio_series = volume_ratio(df["Volume"], 20)

    close_last = close.iloc[-1]
    sma200_last = sma200.iloc[-1]
    ema8_last = ema8.iloc[-1]
    ema21_last = ema21.iloc[-1]
    rsi_last = rsi_series.iloc[-1]
    atr_last = atr_series.iloc[-1]
    vol_ratio_last = vol_ratio_series.iloc[-1]

    above_sma200 = bool(not np.isnan(sma200_last) and close_last > sma200_last)
    ema_cloud_green = (
        bool(cloud_green.iloc[-1]) if not pd.isna(cloud_green.iloc[-1]) else False
    )
    bullish_regime = above_sma200 and ema_cloud_green

    no_trade_zone = bool(not np.isnan(rsi_last) and rsi_last > 70)
    rsi_pullback_ok = bool(not np.isnan(rsi_last) and rsi_last < 50)

    if np.isnan(atr_last) or atr_last == 0 or np.isnan(ema21_last):
        dist_ema21_atr = np.nan
    else:
        dist_ema21_atr = abs(close_last - ema21_last) / atr_last

    # Price action confirmation can be recent (mode-dependent lookback),
    # but must happen near EMA21 in ATR units.
    lookback = min(price_action_lookback, len(df))
    near_ema21_ok = False
    price_action_ok = False
    price_action_signal = "NONE"

    for offset in range(lookback):
        idx = -1 - offset
        atr_i = atr_series.iloc[idx]
        ema21_i = ema21.iloc[idx]
        close_i = close.iloc[idx]

        if pd.isna(atr_i) or atr_i == 0 or pd.isna(ema21_i):
            continue

        dist_i = abs(close_i - ema21_i) / atr_i
        near_i = dist_i <= near_ema21_max_atr
        if near_i:
            near_ema21_ok = True

        engulf_i = is_bullish_engulfing(df, idx=idx)
        pin_i = is_bullish_pin_bar(df, idx=idx)
        if near_i and (engulf_i or pin_i):
            price_action_ok = True
            if engulf_i:
                price_action_signal = "BULLISH_ENGULFING"
            else:
                price_action_signal = "BULLISH_PIN_BAR"
            break

    volume_ok = bool(
        not np.isnan(vol_ratio_last) and vol_ratio_last >= min_volume_ratio
    )

    alpha_rotation = bool(context.get("alpha_rotation", False)) if context else False
    rs_spy = context.get("rs_spy", np.nan) if context else np.nan
    rs_xlu = context.get("rs_xlu", np.nan) if context else np.nan

    passes_pipeline = all(
        [
            bullish_regime,
            not no_trade_zone,
            rsi_pullback_ok,
            near_ema21_ok,
            price_action_ok,
            volume_ok,
        ]
    )

    strategy = "BULL_PUT_SPREAD" if passes_pipeline else None

    failed_filters: list[str] = []
    if not above_sma200:
        failed_filters.append("below_sma200")
    if not ema_cloud_green:
        failed_filters.append("ema_cloud_not_green")
    if no_trade_zone:
        failed_filters.append("rsi_no_trade_zone")
    if not rsi_pullback_ok:
        failed_filters.append("rsi_not_pullback")
    if not near_ema21_ok:
        failed_filters.append("not_near_ema21")
    if not price_action_ok:
        failed_filters.append("price_action_missing")
    if not volume_ok:
        failed_filters.append("volume_below_threshold")

    primary_failure_reason = failed_filters[0] if failed_filters else None

    return {
        "strategy": strategy,
        "above_sma200": above_sma200,
        "ema8": float(ema8_last) if not np.isnan(ema8_last) else np.nan,
        "ema21": float(ema21_last) if not np.isnan(ema21_last) else np.nan,
        "ema_cloud_green": ema_cloud_green,
        "bullish_regime": bullish_regime,
        "rsi": float(rsi_last) if not np.isnan(rsi_last) else np.nan,
        "rsi_pullback_ok": rsi_pullback_ok,
        "no_trade_zone": no_trade_zone,
        "dist_ema21_atr": (
            float(dist_ema21_atr) if not np.isnan(dist_ema21_atr) else np.nan
        ),
        "near_ema21_ok": near_ema21_ok,
        "price_action_signal": price_action_signal,
        "price_action_ok": price_action_ok,
        "vol_ratio": float(vol_ratio_last) if not np.isnan(vol_ratio_last) else np.nan,
        "volume_ok": volume_ok,
        "volume_ratio_threshold": min_volume_ratio,
        "rs_spy": rs_spy,
        "rs_xlu": rs_xlu,
        "alpha_rotation": alpha_rotation,
        "target_dte_min": 15,
        "target_dte_max": 45,
        "short_delta_min": 0.15,
        "short_delta_max": 0.20,
        "failed_filters": failed_filters,
        "primary_failure_reason": primary_failure_reason,
    }


def classify_put_strategy(
    *,
    mode: str = "core",
    df: pd.DataFrame | None = None,
    context: dict | None = None,
    bullish: bool | None = None,
    rsi_val: float | None = None,
    dist_atr: float | None = None,
    vol_ratio: float | None = None,
) -> str | None:
    if df is not None:
        setup = evaluate_put_setup(df, mode=mode, context=context)
        return setup["strategy"]

    if None in (bullish, rsi_val, dist_atr, vol_ratio):
        raise ValueError(
            "For legacy mode, provide bullish, rsi_val, dist_atr and vol_ratio."
        )

    return _legacy_classify(
        bullish=bool(bullish),
        rsi_val=float(rsi_val),
        dist_atr=float(dist_atr),
        vol_ratio=float(vol_ratio),
        mode=mode,
    )

"""Legacy volatility helpers.

This module sits outside the active `market_scanner` flow and is currently a
cleanup candidate. Keep it only if the legacy scanner still uses it
operationally.
"""


def vol_expansion(df, atr_series, lookback=252):
    current_atr = atr_series.iloc[-1]
    atr_mean = atr_series.rolling(lookback).mean().iloc[-1]
    return current_atr / atr_mean

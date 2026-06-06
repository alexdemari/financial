"""Legacy structure helpers.

This module is not part of the active `market_scanner` architecture and is
currently unreferenced by the current repository flow. Retain it only if the
legacy options scanner still requires it.
"""

import numpy as np
import pandas as pd

from options_tech_scanner.cache_utils import memory


@memory.cache
def recent_swing_low(df: pd.DataFrame, lookback: int = 60) -> float:
    lows = df["Low"].iloc[-lookback:]
    idx = lows.idxmin()
    return lows.loc[idx]


def distance_to_support_from_series(price: float, support: float, atr: float) -> float:
    if atr == 0 or np.isnan(atr):
        return np.nan
    return (price - support) / atr

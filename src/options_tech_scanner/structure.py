import numpy as np
import pandas as pd

from options_tech_scanner.cache_utils import memory


@memory.cache
def recent_swing_low(df: pd.DataFrame, lookback: int = 60) -> float:
    lows = df["Low"].iloc[-lookback:]
    idx = lows.idxmin()
    return lows.loc[idx]


def distance_to_support_from_series(
    price: float,
    support: float,
    atr: float
) -> float:
    if atr == 0 or np.isnan(atr):
        return np.nan
    return (price - support) / atr


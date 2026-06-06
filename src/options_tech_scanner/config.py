"""Legacy scanner constants.

This module is not part of the active `market_scanner` architecture and is
currently not referenced by the current repository flow. Keep it only while
the legacy options scanner still needs it operationally.
"""

LOOKBACK_LONG = 200  # primary trend
LOOKBACK_MID = 50
LOOKBACK_SHORT = 20

RSI_PERIOD = 14
ATR_PERIOD = 14

SUPPORT_LOOKBACK = 120
MIN_DISTANCE_SUPPORT_ATR = 0.5
MAX_DISTANCE_SUPPORT_ATR = 2.0

VOLATILITY_LOOKBACK = 252

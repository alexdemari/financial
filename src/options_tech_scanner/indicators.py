import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def ema_cloud(
    series: pd.Series, fast_period: int = 8, slow_period: int = 21
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = ema(series, fast_period)
    ema_slow = ema(series, slow_period)
    cloud_green = ema_fast > ema_slow
    return ema_fast, ema_slow, cloud_green


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def volume_ratio(volume: pd.Series, window: int = 20) -> pd.Series:
    avg_volume = volume.rolling(window).mean()
    return volume / avg_volume


def dollar_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    return close * volume


def avg_dollar_volume(
    close: pd.Series, volume: pd.Series, window: int = 20
) -> pd.Series:
    return dollar_volume(close, volume).rolling(window).mean()


def is_bullish_engulfing(df: pd.DataFrame, idx: int = -1) -> bool:
    if len(df) < 2:
        return False

    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]

    prev_bearish = prev["Close"] < prev["Open"]
    curr_bullish = curr["Close"] > curr["Open"]
    body_engulfs = (curr["Open"] <= prev["Close"]) and (curr["Close"] >= prev["Open"])

    return bool(prev_bearish and curr_bullish and body_engulfs)


def is_bullish_pin_bar(
    df: pd.DataFrame,
    idx: int = -1,
    min_lower_wick_body_ratio: float = 2.0,
    max_upper_wick_body_ratio: float = 1.0,
) -> bool:
    if df.empty:
        return False

    candle = df.iloc[idx]
    body = abs(candle["Close"] - candle["Open"])
    if body == 0:
        body = 1e-9

    upper_wick = candle["High"] - max(candle["Open"], candle["Close"])
    lower_wick = min(candle["Open"], candle["Close"]) - candle["Low"]

    return bool(
        lower_wick >= (min_lower_wick_body_ratio * body)
        and upper_wick <= (max_upper_wick_body_ratio * body)
        and candle["Close"] >= candle["Open"]
    )


def compute_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]
    volume = df["Volume"]

    sma200 = sma(close, 200)
    ema8, ema21, cloud_green = ema_cloud(close, 8, 21)
    rsi14 = rsi(close, 14)
    atr14 = atr(df, 14)
    vol_ratio20 = volume_ratio(volume, 20)
    adv20 = avg_dollar_volume(close, volume, 20)

    return pd.DataFrame(
        {
            "SMA200": sma200,
            "EMA8": ema8,
            "EMA21": ema21,
            "CLOUD_GREEN": cloud_green,
            "RSI14": rsi14,
            "ATR14": atr14,
            "VOL_RATIO20": vol_ratio20,
            "ADV20_USD": adv20,
        },
        index=df.index,
    )

from options_tech_scanner.indicators import ema_cloud, sma


def bullish_regime(df):
    close = df["Close"]
    sma200 = sma(close, 200)
    ema8, ema21, _ = ema_cloud(close, 8, 21)
    slope = sma200.diff(20)

    return (
        close.iloc[-1] > sma200.iloc[-1]
        and slope.iloc[-1] > 0
        and ema8.iloc[-1] > ema21.iloc[-1]
    )

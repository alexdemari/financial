from options_tech_scanner.indicators import sma

def bullish_regime(df):
    close = df["Close"]
    sma200 = sma(close, 200)
    slope = sma200.diff(20)

    return (
        close.iloc[-1] > sma200.iloc[-1]
        and slope.iloc[-1] > 0
    )

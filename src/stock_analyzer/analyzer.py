import pandas as pd
import pandas_ta as ta

from stock_analyzer.backtest import RSIBacktesting, SMABacktesting
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

class StockDataAnalyzer:
    def __init__(self):
        self._rsi_backtesting = RSIBacktesting()
        self._sma_crossing = SMABacktesting()

    def rsi_backtest(self, df: pd.DataFrame):
        return self._rsi_backtesting.backtest(df)

    def retrieve_data(self, symbol: str) -> pd.DataFrame:
        sdm = StockDataManagerFactory().create_with_update_strategy()
        df = sdm.download_and_save(symbol)
        df.dropna(inplace=True)
        return df

    def sma_crossing_backtest(self, df: pd.DataFrame, short=20, long=50) -> pd.DataFrame:
        return self._sma_crossing.backtest(df, short=short, long=long)

    def check_asset(self, df: pd.DataFrame, symbol: str) -> bool:
        df["RSI"] = ta.rsi(df["Close"], length=14)
        df["MM20"] = df["Close"].rolling(window=20).mean()
        df["VolMedia10"] = df["Volume"].rolling(window=10).mean()
        last_rsi = df["RSI"].dropna().iloc[-1]
        last_close = df["Close"].iloc[-1]
        mm20 = df["MM20"].iloc[-1]
        vol = df["Volume"].iloc[-1]
        vol_m10 = df["VolMedia10"].iloc[-1]

        if last_rsi < 30 and last_close > mm20 and vol > vol_m10:
            return True
        else:
            return False

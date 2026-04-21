import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import pandas_ta as ta

from stock_analyzer.config import RTSignalsConfig
from stock_analyzer.enums import Signal

logger = logging.getLogger(__name__)


@dataclass
class RTSignalResult:
    symbol: str
    date: pd.Timestamp
    close_price: float
    trend: str
    strength: str
    supertrend: float
    adx: Optional[float]
    rsi: Optional[float]
    upper_zone: Optional[float]
    lower_zone: Optional[float]
    confirmation_signal: Signal
    contrarian_signal: Signal
    combined_signal: Signal


class RTSignalGenerator:
    """Port of rt_signals Pine logic for local OHLC DataFrames."""

    REQUIRED_COLUMNS = {"High", "Low", "Close"}

    def __init__(self, config: RTSignalsConfig = None):
        self.config = config or RTSignalsConfig()

    def generate_current_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> Optional[RTSignalResult]:
        historical = self.generate_historical_signals(symbol, df)
        if historical.empty:
            return None

        latest = historical.dropna(subset=["supertrend"]).iloc[-1]

        return RTSignalResult(
            symbol=symbol,
            date=latest["date"],
            close_price=float(latest["close"]),
            trend=str(latest["trend"]),
            strength=str(latest["strength"]),
            supertrend=float(latest["supertrend"]),
            adx=self._optional_float(latest["adx"]),
            rsi=self._optional_float(latest["rsi"]),
            upper_zone=self._optional_float(latest["upper_zone"]),
            lower_zone=self._optional_float(latest["lower_zone"]),
            confirmation_signal=Signal(int(latest["confirmation_signal"])),
            contrarian_signal=Signal(int(latest["contrarian_signal"])),
            combined_signal=Signal(int(latest["combined_signal"])),
        )

    def generate_historical_signals(
        self, symbol: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"{symbol}: missing required columns: {sorted(missing)}")

        required_rows = max(
            self.config.sensitivity,
            self.config.zone_period,
            self.config.rsi_period,
            self.config.adx_period + self.config.adx_signal_period,
        )
        if df.empty or len(df) < required_rows:
            logger.warning(f"{symbol}: insufficient data for RT signals")
            return pd.DataFrame()

        result = self._prepare_frame(df)

        supertrend = ta.supertrend(
            result["High"],
            result["Low"],
            result["Close"],
            length=self.config.sensitivity,
            multiplier=self.config.multiplier,
        )
        supertrend_col = f"SUPERT_{self.config.sensitivity}_{self.config.multiplier}"
        direction_col = f"SUPERTd_{self.config.sensitivity}_{self.config.multiplier}"
        result["supertrend"] = supertrend[supertrend_col]
        result["supertrend_direction"] = supertrend[direction_col]

        result["basis"] = result["Close"].rolling(self.config.zone_period).mean()
        zone_dev = self.config.zone_stdev * result["Close"].rolling(
            self.config.zone_period
        ).std(ddof=0)
        result["upper_zone"] = result["basis"] + zone_dev
        result["lower_zone"] = result["basis"] - zone_dev

        adx = ta.adx(
            result["High"],
            result["Low"],
            result["Close"],
            length=self.config.adx_period,
            lensig=self.config.adx_signal_period,
        )
        result["adx"] = adx[f"ADX_{self.config.adx_period}"]
        result["rsi"] = ta.rsi(result["Close"], length=self.config.rsi_period)

        # pandas_ta uses +1 for bullish supertrend, while TradingView's
        # ta.supertrend direction is inverted in the Pine script.
        result["trend_bullish"] = result["supertrend_direction"] > 0
        result["trend_bearish"] = result["supertrend_direction"] < 0
        result["trend"] = result["trend_bullish"].map(
            {True: "BULLISH", False: "BEARISH"}
        )
        result["is_strong"] = result["adx"] > self.config.strong_adx_threshold
        result["strength"] = result["is_strong"].map({True: "STRONG", False: "NORMAL"})

        result["confirmation_buy"] = self._crossover(
            result["Close"], result["supertrend"]
        )
        result["confirmation_sell"] = self._crossunder(
            result["Close"], result["supertrend"]
        )
        result["contrarian_buy"] = (result["Low"] <= result["lower_zone"]) & (
            result["rsi"] < self.config.rsi_buy_threshold
        )
        result["contrarian_sell"] = (result["High"] >= result["upper_zone"]) & (
            result["rsi"] > self.config.rsi_sell_threshold
        )

        if self.config.use_trend_filter:
            result["valid_buy"] = result["confirmation_buy"] & (
                result["adx"] > self.config.adx_filter_threshold
            )
            result["valid_sell"] = result["confirmation_sell"] & (
                result["adx"] > self.config.adx_filter_threshold
            )
        else:
            result["valid_buy"] = result["confirmation_buy"]
            result["valid_sell"] = result["confirmation_sell"]

        result["confirmation_signal"] = Signal.HOLD
        result.loc[result["valid_buy"], "confirmation_signal"] = Signal.BUY
        result.loc[result["valid_sell"], "confirmation_signal"] = Signal.SELL

        result["contrarian_signal"] = Signal.HOLD
        result.loc[result["contrarian_buy"], "contrarian_signal"] = Signal.BUY
        result.loc[result["contrarian_sell"], "contrarian_signal"] = Signal.SELL

        result["combined_signal"] = result["confirmation_signal"]
        no_confirmation = result["combined_signal"] == Signal.HOLD
        result.loc[no_confirmation, "combined_signal"] = result.loc[
            no_confirmation, "contrarian_signal"
        ]

        return result[
            [
                "date",
                "close",
                "supertrend",
                "supertrend_direction",
                "trend",
                "adx",
                "is_strong",
                "strength",
                "basis",
                "upper_zone",
                "lower_zone",
                "rsi",
                "confirmation_buy",
                "confirmation_sell",
                "contrarian_buy",
                "contrarian_sell",
                "confirmation_signal",
                "contrarian_signal",
                "combined_signal",
            ]
        ].astype(
            {
                "confirmation_signal": int,
                "contrarian_signal": int,
                "combined_signal": int,
            }
        )

    @staticmethod
    def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result.reset_index(inplace=True)
        if "Date" in result.columns:
            result.rename(columns={"Date": "date"}, inplace=True)
        elif "index" in result.columns:
            result.rename(columns={"index": "date"}, inplace=True)
        result = result.sort_values("date").reset_index(drop=True)
        result["close"] = result["Close"]
        return result

    @staticmethod
    def _crossover(left: pd.Series, right: pd.Series) -> pd.Series:
        return (left > right) & (left.shift(1) <= right.shift(1))

    @staticmethod
    def _crossunder(left: pd.Series, right: pd.Series) -> pd.Series:
        return (left < right) & (left.shift(1) >= right.shift(1))

    @staticmethod
    def _optional_float(value) -> Optional[float]:
        if pd.isna(value):
            return None
        return float(value)

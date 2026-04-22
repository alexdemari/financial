from dataclasses import dataclass
from typing import Optional

import pandas as pd

from stock_analyzer.enums import Signal
from stock_analyzer.signals.base import AnalyzerSignalResult
from trading_indicators import LuxConfig, LuxSignalsOverlays
from trading_indicators.utils.types import Trend


@dataclass
class LuxSignalResult(AnalyzerSignalResult):
    trend: str
    strength: str
    supertrend: float | None
    adx: Optional[float]
    rsi: Optional[float]
    upper_zone: Optional[float]
    lower_zone: Optional[float]
    confirmation_signal: Signal
    contrarian_signal: Signal
    combined_signal: Signal


class LuxSignalGenerator:
    """Adapter between stock_analyzer and trading_indicators.LuxSignalsOverlays."""

    REQUIRED_COLUMNS = {"Open", "High", "Low", "Close"}

    def __init__(self, config: LuxConfig = None):
        self.config = config or LuxConfig()
        self.indicator = LuxSignalsOverlays(self.config)

    def generate_current_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> Optional[LuxSignalResult]:
        historical = self.generate_historical_signals(symbol, df)
        if historical.empty:
            return None

        latest = historical.dropna(subset=["supertrend"]).iloc[-1]
        return LuxSignalResult(
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

    def interpret(self, signal: LuxSignalResult) -> str:
        combined = self._signal_label(signal.combined_signal)
        trend = str(signal.trend).lower()
        strength = str(signal.strength).lower()
        confirmation = self._signal_label(signal.confirmation_signal)
        contrarian = self._signal_label(signal.contrarian_signal)

        if combined == "BUY":
            if confirmation == "BUY":
                return f"{trend} trend with a {strength} confirmation buy."
            if contrarian == "BUY":
                return f"{trend} trend with a contrarian buy at a reversal zone."

        if combined == "SELL":
            if confirmation == "SELL":
                return f"{trend} trend with a {strength} confirmation sell."
            if contrarian == "SELL":
                return f"{trend} trend with a contrarian sell at a reversal zone."

        return f"{trend} trend, {strength} strength, no active entry signal."

    def recent_columns(self) -> list[str]:
        return ["date", "close", "trend", "adx", "rsi", "combined_signal"]

    def event_columns(self) -> list[str]:
        return ["date", "close", "trend", "adx", "combined_signal"]

    def generate_historical_signals(
        self, symbol: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"{symbol}: missing required columns: {sorted(missing)}")

        prepared = self._prepare_frame(df)
        result = self.indicator.compute(prepared)

        history = pd.DataFrame(index=prepared.index)
        history["date"] = prepared.index
        history["close"] = prepared["close"]
        history["supertrend"] = result.supertrend
        history["supertrend_direction"] = result.trend.map(
            {
                Trend.BULLISH: -1,
                Trend.BEARISH: 1,
                Trend.NEUTRAL: 0,
            }
        )
        history["trend"] = result.trend.map(lambda trend: trend.name)
        history["adx"] = result.adx
        history["is_strong"] = result.is_strong
        history["strength"] = result.is_strong.map({True: "STRONG", False: "NORMAL"})
        history["basis"] = result.basis
        history["upper_zone"] = result.upper_zone
        history["lower_zone"] = result.lower_zone
        history["rsi"] = result.rsi
        history["confirmation_buy"] = result.signal_buy
        history["confirmation_sell"] = result.signal_sell
        history["contrarian_buy"] = result.contra_buy
        history["contrarian_sell"] = result.contra_sell

        history["confirmation_signal"] = Signal.HOLD
        history.loc[result.valid_buy, "confirmation_signal"] = Signal.BUY
        history.loc[result.valid_sell, "confirmation_signal"] = Signal.SELL

        history["contrarian_signal"] = Signal.HOLD
        history.loc[result.contra_buy, "contrarian_signal"] = Signal.BUY
        history.loc[result.contra_sell, "contrarian_signal"] = Signal.SELL

        history["combined_signal"] = history["confirmation_signal"]
        no_confirmation = history["combined_signal"] == Signal.HOLD
        history.loc[no_confirmation, "combined_signal"] = history.loc[
            no_confirmation, "contrarian_signal"
        ]

        return history.astype(
            {
                "confirmation_signal": int,
                "contrarian_signal": int,
                "combined_signal": int,
            }
        ).reset_index(drop=True)

    @staticmethod
    def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )

    @staticmethod
    def _optional_float(value) -> Optional[float]:
        if pd.isna(value):
            return None
        return float(value)

    @staticmethod
    def _signal_label(value) -> str:
        labels = {
            Signal.BUY: "BUY",
            Signal.SELL: "SELL",
            Signal.HOLD: "HOLD",
            1: "BUY",
            -1: "SELL",
            0: "HOLD",
        }
        return labels.get(value, str(value))

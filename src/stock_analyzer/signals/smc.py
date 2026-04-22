from dataclasses import dataclass
from typing import Optional

import pandas as pd

from stock_analyzer.enums import Signal
from stock_analyzer.signals.base import AnalyzerSignalResult
from trading_indicators import SMCConfig, SmartMoneyConfluence


@dataclass
class SMCSignalResult(AnalyzerSignalResult):
    bias: str
    range_position_pct: float | None
    rsi: float | None
    ema200: float | None
    options_hint: str
    swing_high_marker: bool
    swing_low_marker: bool
    in_premium: bool
    in_discount: bool
    bullish_rejection: bool
    bearish_rejection: bool
    bullish_divergence: bool
    bearish_divergence: bool
    long_signal: bool
    short_signal: bool


class SMCSignalGenerator:
    """Adapter between stock_analyzer and trading_indicators.SmartMoneyConfluence."""

    REQUIRED_COLUMNS = {"Open", "High", "Low", "Close"}

    def __init__(self, config: SMCConfig = None):
        self.config = config or SMCConfig()
        self.indicator = SmartMoneyConfluence(self.config)

    def generate_current_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> Optional[SMCSignalResult]:
        historical = self.generate_historical_signals(symbol, df)
        if historical.empty:
            return None

        latest = historical.iloc[-1]
        return SMCSignalResult(
            symbol=symbol,
            date=latest["date"],
            close_price=float(latest["close"]),
            combined_signal=Signal(int(latest["combined_signal"])),
            bias=str(latest["signal_bias"]),
            range_position_pct=self._optional_float(latest["range_position_pct"]),
            rsi=self._optional_float(latest["rsi"]),
            ema200=self._optional_float(latest["ema200"]),
            options_hint=str(latest["options_hint"]),
            swing_high_marker=bool(latest["swing_high_marker"]),
            swing_low_marker=bool(latest["swing_low_marker"]),
            in_premium=bool(latest["in_premium"]),
            in_discount=bool(latest["in_discount"]),
            bullish_rejection=bool(latest["bullish_rejection"]),
            bearish_rejection=bool(latest["bearish_rejection"]),
            bullish_divergence=bool(latest["bullish_divergence"]),
            bearish_divergence=bool(latest["bearish_divergence"]),
            long_signal=bool(latest["long_signal"]),
            short_signal=bool(latest["short_signal"]),
        )

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
        history["rsi"] = result.rsi
        history["ema200"] = result.ema200
        history["range_position_pct"] = self._range_position_pct(
            prepared["close"], result.range_high, result.range_low
        )
        history["swing_high_marker"] = result.swing_highs.notna()
        history["swing_low_marker"] = result.swing_lows.notna()
        history["in_premium"] = result.in_premium
        history["in_discount"] = result.in_discount
        history["bullish_rejection"] = result.bullish_rejection
        history["bearish_rejection"] = result.bearish_rejection
        history["bullish_divergence"] = result.bullish_divergence
        history["bearish_divergence"] = result.bearish_divergence
        history["long_signal"] = result.long_signal
        history["short_signal"] = result.short_signal

        history["combined_signal"] = Signal.HOLD
        history.loc[history["long_signal"], "combined_signal"] = Signal.BUY
        history.loc[history["short_signal"], "combined_signal"] = Signal.SELL

        history["signal_bias"] = "NEUTRAL"
        history.loc[history["long_signal"], "signal_bias"] = "BULLISH"
        history.loc[history["short_signal"], "signal_bias"] = "BEARISH"

        history["signal_context"] = history.apply(self._signal_context, axis=1)
        history["options_hint"] = history.apply(self._options_hint, axis=1)

        return history.astype({"combined_signal": int}).reset_index(drop=True)

    def interpret(self, signal: SMCSignalResult) -> str:
        if signal.long_signal:
            return "bullish structure continuation."
        if signal.short_signal:
            return "premium reversal watch with bearish confluence."
        if signal.in_discount and signal.bullish_rejection:
            return "discount bounce watch."
        if signal.in_premium and signal.bearish_rejection:
            return "premium reversal watch."
        return "no-trade zone."

    def recent_columns(self) -> list[str]:
        return [
            "date",
            "close",
            "signal_bias",
            "signal_context",
            "options_hint",
            "range_position_pct",
            "rsi",
            "swing_high_marker",
            "swing_low_marker",
            "combined_signal",
        ]

    def event_columns(self) -> list[str]:
        return [
            "date",
            "close",
            "signal_bias",
            "signal_context",
            "options_hint",
            "range_position_pct",
            "swing_high_marker",
            "swing_low_marker",
            "combined_signal",
        ]

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
    def _range_position_pct(
        close: pd.Series, range_high: pd.Series, range_low: pd.Series
    ) -> pd.Series:
        span = range_high - range_low
        pct = ((close - range_low) / span) * 100
        return pct.where(span != 0, 50.0)

    @staticmethod
    def _signal_context(row: pd.Series) -> str:
        if row["long_signal"]:
            return "bullish_confluence"
        if row["short_signal"]:
            return "bearish_confluence"
        if row["swing_low_marker"] and row["in_discount"]:
            return "short_term_bullish_reversal"
        if row["swing_high_marker"] and row["in_premium"]:
            return "short_term_bearish_reversal"
        if row["in_discount"] and row["bullish_rejection"]:
            return "discount_watch"
        if row["in_premium"] and row["bearish_rejection"]:
            return "premium_watch"
        if row["swing_low_marker"]:
            return "swing_low_watch"
        if row["swing_high_marker"]:
            return "swing_high_watch"
        return "no_trade"

    @staticmethod
    def _options_hint(row: pd.Series) -> str:
        if row["long_signal"]:
            return "CALL"
        if row["short_signal"]:
            return "PUT"
        if row["swing_low_marker"] or (row["in_discount"] and row["bullish_rejection"]):
            return "CALL_WATCH"
        if row["swing_high_marker"] or (row["in_premium"] and row["bearish_rejection"]):
            return "PUT_WATCH"
        return "NO_TRADE"

    @staticmethod
    def _optional_float(value) -> Optional[float]:
        if pd.isna(value):
            return None
        return float(value)

"""
Gerador de sinais RSI/SMA legado.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from stock_analyzer.config import IndicatorConfig
from stock_analyzer.enums import Signal
from stock_analyzer.indicators import IndicatorCalculator
from stock_analyzer.signals.base import AnalyzerSignalResult

logger = logging.getLogger(__name__)


@dataclass
class SignalResult(AnalyzerSignalResult):
    """Resultado de um sinal RSI/SMA normalizado."""

    rsi_value: Optional[float]
    sma_value: Optional[float]
    rsi_signal: Signal
    sma_signal: Signal
    combined_signal: Signal


class SignalGenerator:
    """
    Gera sinais RSI/SMA normalizados.
    """

    def __init__(self, config: IndicatorConfig = None):
        self.config = config or IndicatorConfig()
        self.calculator = IndicatorCalculator()

    def _get_rsi_signal(self, rsi_value: float) -> Signal:
        """Converte valor RSI para sinal."""
        if pd.isna(rsi_value):
            return Signal.HOLD
        if rsi_value < self.config.rsi_buy_threshold:
            return Signal.BUY
        elif rsi_value > self.config.rsi_sell_threshold:
            return Signal.SELL
        return Signal.HOLD

    def _get_sma_signal(self, close: float, sma: float) -> Signal:
        """Converte comparacao Close/SMA para sinal."""
        if pd.isna(close) or pd.isna(sma):
            return Signal.HOLD
        if close > sma:
            return Signal.BUY
        elif close < sma:
            return Signal.SELL
        return Signal.HOLD

    def generate_current_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> Optional[SignalResult]:
        """Gera sinal para o ultimo candle."""
        if df.empty:
            logger.warning(f"{symbol}: DataFrame vazio")
            return None

        required_rows = max(self.config.rsi_period, self.config.sma_period)
        if len(df) < required_rows:
            logger.warning(
                f"{symbol}: Insuficientes dados. "
                f"Necessario: {required_rows}, Recebido: {len(df)}"
            )
            return None

        df_calc = df.copy()
        df_calc["RSI"] = self.calculator.calculate_rsi(
            df_calc["Close"], self.config.rsi_period
        )
        df_calc["SMA"] = self.calculator.calculate_sma(
            df_calc["Close"], self.config.sma_period
        )

        try:
            latest = df_calc.dropna().iloc[-1]
        except IndexError:
            logger.error(f"{symbol}: Falha ao obter ultima linha")
            return None

        close = latest["Close"]
        rsi = latest["RSI"]
        sma = latest["SMA"]

        rsi_signal = self._get_rsi_signal(rsi)
        sma_signal = self._get_sma_signal(close, sma)

        if rsi_signal == Signal.BUY and sma_signal == Signal.BUY:
            combined = Signal.BUY
        elif rsi_signal == Signal.SELL and sma_signal == Signal.SELL:
            combined = Signal.SELL
        else:
            combined = Signal.HOLD

        return SignalResult(
            symbol=symbol,
            date=latest.name,
            close_price=close,
            rsi_value=rsi,
            sma_value=sma,
            rsi_signal=rsi_signal,
            sma_signal=sma_signal,
            combined_signal=combined,
        )

    def generate_historical_signals(
        self, symbol: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        """Gera serie historica de sinais."""
        if df.empty:
            logger.warning(f"{symbol}: DataFrame vazio para historico")
            return pd.DataFrame()

        required_rows = max(self.config.rsi_period, self.config.sma_period)
        if len(df) < required_rows:
            logger.warning(f"{symbol}: Historico insuficiente")
            return pd.DataFrame()

        df_hist = df.copy()
        df_hist.reset_index(inplace=True)

        if "Date" in df_hist.columns:
            df_hist.rename(columns={"Date": "date"}, inplace=True)

        df_hist = df_hist.sort_values("date").reset_index(drop=True)

        df_hist["rsi"] = self.calculator.calculate_rsi(
            df_hist["Close"], self.config.rsi_period
        )
        df_hist["sma"] = self.calculator.calculate_sma(
            df_hist["Close"], self.config.sma_period
        )

        df_hist["rsi_signal"] = df_hist["rsi"].apply(self._get_rsi_signal).astype(int)
        df_hist["sma_signal"] = (
            df_hist["Close"].combine(df_hist["sma"], self._get_sma_signal).astype(int)
        )

        df_hist["combined_signal"] = df_hist.apply(
            lambda row: Signal.BUY
            if (row["rsi_signal"] == Signal.BUY and row["sma_signal"] == Signal.BUY)
            else (
                Signal.SELL
                if (
                    row["rsi_signal"] == Signal.SELL
                    and row["sma_signal"] == Signal.SELL
                )
                else Signal.HOLD
            ),
            axis=1,
        ).astype(int)

        return df_hist[
            [
                "date",
                "Close",
                "rsi",
                "sma",
                "rsi_signal",
                "sma_signal",
                "combined_signal",
            ]
        ].rename(columns={"Close": "close"})

    def interpret(self, signal: SignalResult) -> str:
        combined = self._signal_label(signal.combined_signal)
        rsi_signal = self._signal_label(signal.rsi_signal)
        sma_signal = self._signal_label(signal.sma_signal)

        if combined == "BUY":
            return "RSI and SMA are aligned on a buy."
        if combined == "SELL":
            return "RSI and SMA are aligned on a sell."
        if rsi_signal == sma_signal and rsi_signal != "HOLD":
            return (
                f"RSI and SMA are aligned on {rsi_signal.lower()}, "
                "but no combined trigger was emitted."
            )
        return "RSI and SMA are not aligned, so the model remains on hold."

    def recent_columns(self) -> list[str]:
        return ["date", "close", "rsi", "sma", "combined_signal"]

    def event_columns(self) -> list[str]:
        return ["date", "close", "rsi", "sma", "combined_signal"]

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

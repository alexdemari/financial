"""
Cálculo de indicadores técnicos (separação de responsabilidades).
"""

import logging
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """Responsável apenas por calcular indicadores."""

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI."""
        if series.empty or len(series) < period:
            logger.warning(f"Série insuficiente para RSI(período={period})")
            return pd.Series([None] * len(series), index=series.index)

        return ta.rsi(series, length=period)

    @staticmethod
    def calculate_sma(series: pd.Series, period: int = 50) -> pd.Series:
        """Calcula SMA."""
        if series.empty or len(series) < period:
            logger.warning(f"Série insuficiente para SMA(período={period})")
            return pd.Series([None] * len(series), index=series.index)

        return ta.sma(series, length=period)

    @staticmethod
    def calculate_cci(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calcula CCI."""
        if any(s.empty for s in [high, low, close]) or len(close) < period:
            logger.warning(f"Série insuficiente para CCI(período={period})")
            return pd.Series([None] * len(close), index=close.index)

        return ta.cci(high, low, close, length=period)

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from stock_analyzer.enums import Signal


@dataclass
class AnalyzerSignalResult:
    symbol: str
    date: pd.Timestamp
    close_price: float
    combined_signal: Signal


def latest_historical_row(
    historical: pd.DataFrame, *, dropna_column: str | None = None
) -> pd.Series | None:
    """Return the current historical row, or ``None`` when no signal exists."""
    if historical.empty:
        return None
    if dropna_column is not None:
        historical = historical.dropna(subset=[dropna_column])
        if historical.empty:
            return None
    return historical.iloc[-1]


@runtime_checkable
class AnalyzerSignalAdapter(Protocol):
    def generate_current_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> AnalyzerSignalResult | None:
        ...

    def generate_historical_signals(
        self, symbol: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        ...

    def generate_current_signal_from_historical(
        self, symbol: str, historical: pd.DataFrame
    ) -> AnalyzerSignalResult | None:
        ...

    def interpret(self, signal: Any) -> str:
        ...

    def recent_columns(self) -> list[str]:
        ...

    def event_columns(self) -> list[str]:
        ...

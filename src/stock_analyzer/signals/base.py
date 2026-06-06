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

    def interpret(self, signal: Any) -> str:
        ...

    def recent_columns(self) -> list[str]:
        ...

    def event_columns(self) -> list[str]:
        ...

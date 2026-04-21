"""
Contrato base para todos os indicadores.
Aplica o padrão Template Method: subclasses implementam `_validate` e `_compute`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import pandas as pd

T = TypeVar("T")

REQUIRED_COLUMNS = {"open", "high", "low", "close"}


class BaseIndicator(ABC, Generic[T]):
    """
    Classe base para indicadores técnicos.

    Responsabilidades:
      - Validar o DataFrame de entrada (Template Method)
      - Delegar o cálculo para a subclasse
      - Expor uma interface uniforme via `compute()`
    """

    def compute(self, df: pd.DataFrame) -> T:
        """
        Ponto de entrada público.

        Args:
            df: DataFrame com colunas OHLCV (case-insensitive).
                O índice deve ser DatetimeIndex ou inteiro crescente.

        Returns:
            Objeto de resultado tipado conforme a subclasse.
        """
        df = self._normalize_columns(df)
        self._validate(df)
        return self._compute(df)

    # ── Template Method ────────────────────────────────────────────────────────

    def _validate(self, df: pd.DataFrame) -> None:
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame está faltando colunas: {missing}")
        if len(df) < self._min_bars():
            raise ValueError(
                f"{self.__class__.__name__} requer ao menos {self._min_bars()} barras; "
                f"recebeu {len(df)}."
            )

    @abstractmethod
    def _compute(self, df: pd.DataFrame) -> T:
        """Implementação do cálculo do indicador."""

    def _min_bars(self) -> int:
        """Mínimo de barras necessárias. Sobrescreva se necessário."""
        return 1

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(columns=str.lower)

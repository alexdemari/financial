"""
Agregador de sinais — combina múltiplos indicadores via Strategy + Composite.

Permite criar estratégias compostas a partir dos indicadores individuais
sem acoplar o código do consumidor às implementações concretas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from trading_indicators.utils.types import LuxResult, SMCResult, SignalType


# ─── Protocolo de estratégia de sinal ─────────────────────────────────────────


class SignalStrategy(Protocol):
    """Contrato para qualquer gerador de sinais."""

    def generate(self, df: pd.DataFrame) -> pd.Series:
        """Retorna uma Series de SignalType por candle."""
        ...


# ─── Implementações concretas ──────────────────────────────────────────────────


class SMCSignalStrategy:
    """Extrai sinais do SMC já computado."""

    def __init__(self, result: SMCResult) -> None:
        self._result = result

    def generate(self, df: pd.DataFrame) -> pd.Series:
        r = self._result
        signals = pd.Series(SignalType.NONE, index=df.index)
        signals[r.long_signal] = SignalType.BUY
        signals[r.short_signal] = SignalType.SELL
        return signals


class LuxSignalStrategy:
    """Extrai sinais do Lux já computado, incluindo força e contrarians."""

    def __init__(self, result: LuxResult) -> None:
        self._result = result

    def generate(self, df: pd.DataFrame) -> pd.Series:
        r = self._result
        signals = pd.Series(SignalType.NONE, index=df.index)

        # Ordem importa: sinais mais específicos sobrescrevem os genéricos
        signals[r.valid_buy] = SignalType.BUY
        signals[r.valid_sell] = SignalType.SELL
        signals[r.valid_buy & r.is_strong] = SignalType.STRONG_BUY
        signals[r.valid_sell & r.is_strong] = SignalType.STRONG_SELL
        signals[r.contra_buy] = SignalType.CONTRA_BUY
        signals[r.contra_sell] = SignalType.CONTRA_SELL

        return signals


# ─── Agregador Composto ────────────────────────────────────────────────────────


@dataclass
class AggregationRule:
    """Define como múltiplos sinais são combinados."""

    require_agreement: bool = True  # True = todos devem concordar
    min_strategies: int = 1  # Mínimo de estratégias com sinal ativo


class CompositeSignalAggregator:
    """
    Agrega sinais de múltiplas estratégias (Composite Pattern).

    Uso::

        aggregator = CompositeSignalAggregator(rule=AggregationRule(require_agreement=True))
        aggregator.add(SMCSignalStrategy(smc_result))
        aggregator.add(LuxSignalStrategy(lux_result))

        signals = aggregator.aggregate(df)
        confirmed_buys = df[signals == SignalType.BUY]
    """

    def __init__(self, rule: AggregationRule | None = None) -> None:
        self._strategies: list[SignalStrategy] = []
        self.rule = rule or AggregationRule()

    def add(self, strategy: SignalStrategy) -> "CompositeSignalAggregator":
        """Fluent interface para encadear adições."""
        self._strategies.append(strategy)
        return self

    def aggregate(self, df: pd.DataFrame) -> pd.Series:
        """
        Combina todos os sinais conforme a regra configurada.

        Returns:
            Series com SignalType por candle.
        """
        if not self._strategies:
            raise RuntimeError("Nenhuma estratégia adicionada ao agregador.")

        all_signals = pd.DataFrame(
            {i: s.generate(df) for i, s in enumerate(self._strategies)}
        )

        buy_types = {SignalType.BUY, SignalType.STRONG_BUY, SignalType.CONTRA_BUY}
        sell_types = {SignalType.SELL, SignalType.STRONG_SELL, SignalType.CONTRA_SELL}

        n_strategies = len(self._strategies)
        result = pd.Series(SignalType.NONE, index=df.index)

        for idx in df.index:
            row = all_signals.loc[idx]
            buy_count = sum(1 for v in row if v in buy_types)
            sell_count = sum(1 for v in row if v in sell_types)

            if self.rule.require_agreement:
                if buy_count == n_strategies:
                    result[idx] = SignalType.BUY
                elif sell_count == n_strategies:
                    result[idx] = SignalType.SELL
            else:
                if buy_count >= self.rule.min_strategies:
                    result[idx] = SignalType.BUY
                elif sell_count >= self.rule.min_strategies:
                    result[idx] = SignalType.SELL

        return result

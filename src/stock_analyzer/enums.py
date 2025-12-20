"""
Enumerações para o módulo de análise.
"""
from enum import IntEnum, auto


class Signal(IntEnum):
    """Sinais de trading normalizados."""
    BUY = 1
    SELL = -1
    HOLD = 0


class SignalSource(IntEnum):
    """Fonte do sinal (RSI ou SMA)."""
    RSI = auto()
    SMA = auto()
    COMBINED = auto()
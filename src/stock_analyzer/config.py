"""
Configurações centralizadas para o módulo de análise.
"""
from dataclasses import dataclass


@dataclass
class IndicatorConfig:
    """Configuração de indicadores técnicos."""
    rsi_period: int = 14
    rsi_buy_threshold: float = 30.0
    rsi_sell_threshold: float = 70.0
    sma_period: int = 50
    sma_short_period: int = 20
    sma_long_period: int = 50


@dataclass
class BacktestConfig:
    """Configuração de backtesting."""
    initial_capital: float = 10000.0
    commission_rate: float = 0.001
    cci_period: int = 14
    cci_low_threshold: float = -100.0
    cci_high_threshold: float = 100.0
    risked_money: float = 500.0


@dataclass
class RSIBacktestConfig:
    """Configuração específica para backtesting RSI."""
    initial_capital: float = 10000.0
    commission_rate: float = 0.001
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    use_extreme_reversal: bool = True  # Usar reversão extrema (saída de zona)


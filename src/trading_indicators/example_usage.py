"""
Exemplo de uso da biblioteca trading_indicators.

Demonstra os três padrões principais de consumo:
  1. Indicador standalone
  2. Dois indicadores independentes
  3. Agregador composto com confluência
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from trading_indicators import (
    AggregationRule,
    CompositeSignalAggregator,
    LuxConfig,
    LuxSignalStrategy,
    LuxSignalsOverlays,
    SMCConfig,
    SMCSignalStrategy,
    SmartMoneyConfluence,
)
from trading_indicators.utils.types import SignalType

# ── Setup: DataFrame OHLCV sintético ──────────────────────────────────────────
rng = np.random.default_rng(42)
n = 600
dates = pd.date_range("2024-01-01", periods=n, freq="1h")
close = 50_000 + np.cumsum(rng.normal(0, 200, n))  # simula BTC/BRL
spread = rng.uniform(50, 500, n)

df = pd.DataFrame(
    {
        "open": close - rng.uniform(-100, 100, n),
        "high": close + spread,
        "low": close - spread,
        "close": close,
        "volume": rng.uniform(0.5, 10.0, n),
    },
    index=dates,
)

print(f"Dataset: {len(df)} barras | {df.index[0]} → {df.index[-1]}\n")

# ─────────────────────────────────────────────────────────────────────────────
# Padrão 1: SMC standalone
# ─────────────────────────────────────────────────────────────────────────────
smc = SmartMoneyConfluence(SMCConfig(swing_lookback=10, use_ema_filter=True))
smc_result = smc.compute(df)

print("=== Smart Money Confluence ===")
print(f"RSI atual:          {smc_result.rsi:.2f}")
print(f"Posição no range:   {smc_result.range_position_pct:.1f}%")
print(f"Sinais de compra:   {smc_result.long_signal.sum()}")
print(f"Sinais de venda:    {smc_result.short_signal.sum()}")

if smc_result.long_signal.any():
    last_buy = df[smc_result.long_signal].index[-1]
    print(f"Último sinal BUY:   {last_buy} @ {df.loc[last_buy, 'close']:.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# Padrão 2: Lux standalone
# ─────────────────────────────────────────────────────────────────────────────
lux = LuxSignalsOverlays(
    LuxConfig(sensitivity=14, multiplier=1.5, use_trend_filter=True)
)
lux_result = lux.compute(df)

last_trend = lux_result.trend.iloc[-1]
print("\n=== Lux Signals & Overlays ===")
print(f"Tendência atual:    {last_trend.name if last_trend else 'N/A'}")
print(f"ADX atual:          {lux_result.adx.iloc[-1]:.2f}")
print(f"RSI atual:          {lux_result.rsi.iloc[-1]:.2f}")
print(f"Compras válidas:    {lux_result.valid_buy.sum()}")
print(f"Compras fortes:     {(lux_result.valid_buy & lux_result.is_strong).sum()}")
print(f"Vendas válidas:     {lux_result.valid_sell.sum()}")
print(f"Contra-compras:     {lux_result.contra_buy.sum()}")
print(f"Contra-vendas:      {lux_result.contra_sell.sum()}")

# ─────────────────────────────────────────────────────────────────────────────
# Padrão 3: Agregador composto — confluência dos dois indicadores
# ─────────────────────────────────────────────────────────────────────────────
agg = (
    CompositeSignalAggregator(AggregationRule(require_agreement=True))
    .add(SMCSignalStrategy(smc_result))
    .add(LuxSignalStrategy(lux_result))
)

combined = agg.aggregate(df)

buy_mask = combined == SignalType.BUY
sell_mask = combined == SignalType.SELL

print("\n=== Confluência SMC + Lux (ambos precisam concordar) ===")
print(f"Sinais de compra confluentes:  {buy_mask.sum()}")
print(f"Sinais de venda confluentes:   {sell_mask.sum()}")

if buy_mask.any():
    last_confluence_buy = df[buy_mask].index[-1]
    print(
        f"Último BUY confluente: {last_confluence_buy} @ {df.loc[last_confluence_buy, 'close']:.2f}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Snapshot da última barra
# ─────────────────────────────────────────────────────────────────────────────
last = df.index[-1]
print(f"\n=== Última barra: {last} ===")
print(f"Close:            {df.loc[last, 'close']:.2f}")
print(f"EMA 200:          {smc_result.ema200.iloc[-1]:.2f}")
print(
    f"Zona:             {'PREMIUM' if smc_result.in_premium.iloc[-1] else 'DISCOUNT'}"
)
print(f"Sinal combinado:  {combined.iloc[-1].name}")

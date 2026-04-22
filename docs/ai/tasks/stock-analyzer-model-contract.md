# Stock Analyzer — Model Contract

## Purpose

Define a minimal, stable contract for all signal models used in `stock_analyzer`.

Goal:

- keep CLI behavior consistent
- avoid model-specific divergence
- enable incremental addition of models (e.g. lux, smc, confluence)

---

## Core Concepts

Each model must provide:

1. Current signal (snapshot)
2. Historical signals (DataFrame)
3. CLI integration helpers

---

## 1. Current Signal (Snapshot)

All models must return an object with the following base fields:

```python
@dataclass
class AnalyzerSignalResult:
    symbol: str
    date: pd.Timestamp
    close_price: float
    combined_signal: Signal  # BUY | SELL | HOLD

# Stock Analyzer — Model Contract

## Purpose

Define a minimal, stable contract for all signal models used in `stock_analyzer`.

Goals:

* keep CLI behavior consistent
* avoid model-specific divergence
* enable incremental addition of models (e.g. `lux`, `smc`, `confluence`)
* keep the analyzer local-first, explicit, and easy to test

---

## Scope

This contract applies to all signal models used by `stock_analyzer`.

It defines:

* the minimum structure of the current signal (snapshot)
* the minimum structure of historical output
* the minimum hooks required for CLI rendering

It does NOT define:

* how each model computes indicators internally
* how data is retrieved or updated
* multi-symbol execution
* confluence logic implementation details

---

## Core Concepts

Each model must provide:

1. Current signal (snapshot)
2. Historical signals (`pandas.DataFrame`)
3. CLI integration helpers

This is a minimal contract, not a framework.

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
```

Models may extend this base shape with model-specific fields.

The CLI must rely on these fields being present for every model.

---

### Example — Lux

```python
@dataclass
class LuxSignalResult(AnalyzerSignalResult):
    trend: str
    strength: str
    supertrend: float | None
    adx: float | None
    rsi: float | None
    upper_zone: float | None
    lower_zone: float | None
    confirmation_signal: Signal
    contrarian_signal: Signal
```

---

### Example — SMC

```python
@dataclass
class SMCSignalResult(AnalyzerSignalResult):
    bias: str
    range_position_pct: float | None
    rsi: float | None
    ema200: float | None

    in_premium: bool
    in_discount: bool

    bullish_rejection: bool
    bearish_rejection: bool

    bullish_divergence: bool
    bearish_divergence: bool

    long_signal: bool
    short_signal: bool
```

---

## 2. Historical Output

All models must return a `pandas.DataFrame` with at least:

| column          | description       |
| --------------- | ----------------- |
| date            | candle timestamp  |
| close           | close price       |
| combined_signal | BUY / SELL / HOLD |

---

### Recommended Common Columns

When applicable:

| column         | description                             |
| -------------- | --------------------------------------- |
| signal_bias    | BULLISH / BEARISH / NEUTRAL             |
| signal_context | short stable label describing the setup |

---

### Model-specific Columns

Each model may append additional columns.

#### Lux (example)

* trend
* strength
* adx
* rsi
* supertrend
* confirmation_signal
* contrarian_signal

#### SMC (example)

* rsi
* ema200
* range_position_pct
* in_premium
* in_discount
* bullish_rejection
* bearish_rejection
* bullish_divergence
* bearish_divergence
* long_signal
* short_signal

---

## 3. CLI Integration Contract

Each model must provide:

```python
class AnalyzerSignalAdapter(Protocol):

    def generate_current_signal(self, symbol: str, df: pd.DataFrame): ...

    def generate_historical_signals(self, symbol: str, df: pd.DataFrame) -> pd.DataFrame: ...

    def interpret(self, signal) -> str: ...

    def recent_columns(self) -> list[str]: ...

    def event_columns(self) -> list[str]: ...
```

This does not require inheritance — a simple consistent implementation is enough.

---

## 4. CLI Output Structure

The CLI must always produce:

1. Interpretation
2. Current Snapshot
3. Recent Rows
4. Recent Signal Events

Each model must support this structure.

---

## 5. Interpretation Contract

Each model must provide a short human-readable interpretation.

Requirements:

* concise
* operational
* stable wording
* terminal-friendly

Examples:

* trend-following buy setup
* contrarian bounce setup
* bullish structure continuation
* premium reversal watch
* no-trade zone

---

## 6. Signal Mapping Rules

### 6.1 combined_signal

Every model must map its logic into:

* BUY
* SELL
* HOLD

#### SMC mapping

* BUY if long_signal == True
* SELL if short_signal == True
* HOLD otherwise

---

### 6.2 signal_bias

Recommended:

* BULLISH
* BEARISH
* NEUTRAL

Conservative mapping (recommended):

* BULLISH if long_signal
* BEARISH if short_signal
* NEUTRAL otherwise

---

### 6.3 signal_context

Short stable labels describing context.

Examples:

* trend_confirmation
* contrarian_reversal
* bullish_confluence
* bearish_confluence
* discount_watch
* premium_watch
* no_trade

---

## 7. SMC-Specific Initial Contract

### Current Snapshot Fields

* symbol
* date
* close_price
* combined_signal
* bias
* range_position_pct
* rsi
* ema200
* in_premium
* in_discount
* bullish_rejection
* bearish_rejection
* bullish_divergence
* bearish_divergence
* long_signal
* short_signal

---

### Historical Fields

* date
* close
* combined_signal
* signal_bias
* signal_context
* rsi
* ema200
* range_position_pct
* in_premium
* in_discount
* bullish_rejection
* bearish_rejection
* bullish_divergence
* bearish_divergence
* long_signal
* short_signal

---

## 8. Adapter Responsibilities

Each adapter must:

* translate model output into the analyzer contract
* define interpretation
* define recent columns
* define event columns

Adapters must NOT:

* download data
* decide update vs local-only
* parse CLI arguments
* implement portfolio logic

---

## 9. Design Constraints

* do not embed model-specific logic in CLI core
* do not break existing models (lux)
* keep contracts minimal and explicit
* avoid overengineering
* prefer incremental evolution

---

## 10. Testing Expectations

Each model must have tests covering:

* snapshot generation
* historical output
* required columns
* combined_signal mapping
* CLI integration
* report rendering

Tests must:

* avoid network
* use in-memory DataFrames
* validate behavior (not implementation)

---

## 11. Non-Goals

This contract does NOT introduce:

* event-driven architecture
* distributed systems
* async processing
* generic signal framework
* confluence implementation
* multi-symbol ranking

---

## Summary

All models must:

* follow a common snapshot contract
* return a consistent historical DataFrame
* expose CLI helpers

This keeps the analyzer:

* predictable
* extensible
* easy to test
* aligned with local-first design

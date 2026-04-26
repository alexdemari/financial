# Logical View

## Overview

The project is composed of loosely coupled modules with clear runtime handoffs.

At a logical level:

```text
stock_data_manager
  ->
local OHLC CSV data
  ->
stock_analyzer
  ->
per-symbol signal history
  ->
market_scanner
  ->
Scanner V3 decisions
  ->
backtest
```

---

## Main Logical Layers

### Data Layer

Module:

- `stock_data_manager`

Role:

- maintain local market data
- expose file-based historical datasets

---

### Signal Layer

Module:

- `stock_analyzer`

Role:

- analyze one symbol at a time
- expose model-specific signal outputs

Important adapters:

- Lux
- SMC
- legacy RSI/SMA

---

### Technical Logic Layer

Module:

- `trading_indicators`

Role:

- implement reusable technical calculations
- stay below scanner orchestration concerns

---

### Decision Layer

Module:

- `market_scanner`

Role:

- convert per-symbol signal outputs into Scanner V3 decisions

Important concepts:

- alignment
- consistency score
- `market_state`
- `adjusted_alignment`
- `action_bucket`

---

### Validation Layer

Module:

- the current backtest module

Role:

- replay historical scanner decisions
- evaluate directional signal quality

---

## Key Shared Artifact

The central logical handoff today is the shared scanner row.

It connects:

- `stock_analyzer` historical outputs
- scanner decision logic
- scanner reporting
- current backtest

This is why scanner and backtest should continue sharing the same row-building
logic.

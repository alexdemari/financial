# Module Boundaries

## Purpose

This document records the practical boundaries between the main local-first
systems in the repository.

The goal is to keep responsibilities clear and avoid logic drifting into the
wrong package.

---

## Boundary Map

```text
stock_data_manager
  -> local data ingestion and persistence

stock_analyzer
  -> single-symbol signal generation

trading_indicators
  -> low-level technical logic

market_scanner
  -> multi-symbol orchestration and decision logic

backtest
  -> signal validation for Scanner V3
```

---

## `stock_data_manager`

Owns:

- downloading OHLC data
- incremental updates
- CSV persistence
- merge strategy behavior

Does not own:

- signal generation
- scanner logic
- ranking
- strategy validation

Rule:

- `stock_data_manager` is the data layer, not the analysis layer.

---

## `stock_analyzer`

Owns:

- one-symbol analysis
- current signal generation
- historical signal generation
- model adapters such as Lux and SMC
- one-symbol CLI reporting

Does not own:

- universe scanning
- Scanner V3 decision fields
- multi-symbol ranking
- candidate/watchlist selection

Rule:

- `stock_analyzer` answers single-symbol questions.

---

## `trading_indicators`

Owns:

- indicator calculations
- Lux implementation details
- SMC implementation details
- reusable technical primitives

Does not own:

- scanner orchestration
- CSV persistence
- universe logic
- report generation

Rule:

- `trading_indicators` is the home of raw technical logic.

---

## `market_scanner`

Owns:

- universe loading
- eligibility filtering
- multi-symbol orchestration
- shared scanner row construction
- Scanner V3 decision logic
- scanner reporting
- signal-quality backtest orchestration

Does not own:

- raw market data download
- low-level Lux calculations
- low-level SMC calculations

Hard rule:

- `market_scanner` MUST NOT implement indicator logic.

`options_tech_scanner` remains in the repository as:

- the legacy scanner namespace
- a temporary compatibility layer for migrated current-scanner modules

It may compose Lux and SMC outputs, but the underlying technical calculations
must remain in `trading_indicators` and be surfaced through `stock_analyzer`
adapters.

---

## Current Backtest

Owns:

- historical replay of Scanner V3 rows
- forward return metrics
- directional win/loss evaluation
- detailed and decision-oriented summaries

Does not own:

- options PnL simulation
- trade execution modeling
- commissions or slippage modeling
- replacing the scanner's decision logic

Rule:

- the current backtest validates signal quality, not options strategy economics.

---

## Shared Rule For Scanner V3

The Scanner V3 row is the shared decision artifact between:

- scanner execution
- scanner reporting
- backtest replay

Rule:

- scanner decision logic should be defined once and reused
- backtest logic should consume scanner decisions, not reimplement them

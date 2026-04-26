# Stock Analyzer

## Purpose

`stock_analyzer` is the single-symbol signal engine of the project.

Its job is to answer:

**"What is this asset signaling now, and what is its recent signal history?"**

It is not a scanner, not a portfolio engine, and not the main home of strategy
backtesting.

---

## Architectural Role

`stock_analyzer` sits between local market data and higher-level decision
systems.

```text
local OHLC CSV
  ->
StockDataAnalyzer
  ->
selected signal model
  ->
current signal + historical signals
```

The package is used in two ways:

- directly, through its CLI for manual symbol inspection
- indirectly, as the per-symbol signal provider used by
  `options_tech_scanner`

---

## Responsibilities

`stock_analyzer` should own:

- single-symbol analysis
- signal model selection
- current signal generation
- historical signal generation
- human-readable CLI inspection for one symbol
- adapter integration with `trading_indicators`

In practice, the important models today are:

- `rsi-sma`
- `lux`
- `smc`

---

## Non-Responsibilities

`stock_analyzer` should NOT own:

- multi-symbol ranking
- Scanner V3 decision fields
- universe filtering
- eligibility logic for scanner runs
- options-oriented orchestration
- scanner reports

These belong elsewhere:

- multi-symbol orchestration -> `options_tech_scanner`
- data ingestion and persistence -> `stock_data_manager`
- low-level indicator logic -> `trading_indicators`

---

## Internal Shape

### `analyzer.py`

Contains `StockDataAnalyzer`, the orchestration layer.

It:

- selects the signal model
- delegates to the selected adapter
- retrieves or loads local data when requested

### `signals/`

Contains model adapters.

- `rsi_sma.py`
  - legacy combined RSI/SMA signal model
- `lux.py`
  - adapter around `trading_indicators.LuxSignalsOverlays`
- `smc.py`
  - adapter around `trading_indicators.SmartMoneyConfluence`

### `main.py`

CLI entry point for one-symbol analysis.

It is intentionally local and manual:

- one symbol at a time
- synchronous
- optional `--local-only`

### `backtest.py`

Contains legacy strategy backtests local to this package.

This file exists, but it should not be treated as the main validation path for
the current scanner. That role now belongs to the current backtest in
`options_tech_scanner`.

---

## Data Contract

For a given symbol, the package exposes:

- one current signal object
- one historical signal DataFrame

This is the key contract consumed by higher layers.

For Scanner V3, the most important behavior is:

- Lux historical output is available
- SMC historical output is available
- those histories can be consumed by `options_tech_scanner` to build a shared
  scanner row

---

## Current Assessment

`stock_analyzer` is in reasonably good shape.

Why:

- role is narrow enough
- Lux and SMC adapters are usable
- local-only CLI works
- tests cover the package behavior

What still needs attention later:

- backtesting code inside this package is secondary and should remain clearly
  separated from Scanner V3 validation
- naming and architecture docs should keep emphasizing that this is a
  single-symbol engine, not a scanner

---

## Rule Of Thumb

If the question is:

- "What does `AAPL` signal now?"
- "Show me recent Lux events for `NVDA`."
- "Inspect one symbol locally."

then it belongs in `stock_analyzer`.

If the question is:

- "Which symbols should I prioritize?"
- "Which assets are candidates or watchlist setups?"
- "Do Scanner V3 signals have edge historically?"

then it belongs in `options_tech_scanner`.

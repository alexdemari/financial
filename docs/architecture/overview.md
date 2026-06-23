# Architecture Overview

## Purpose

The project is a local-first financial analysis system organized as a modular
monolith.

Its current goal is:

- maintain local OHLC datasets
- analyze one symbol at a time with reusable signal models
- scan many symbols with Scanner V3 decision logic
- validate signal quality with the current backtest
- generate a daily actionable report crossing fresh signals with backtest-qualified setups

The codebase is synchronous, CLI-driven, and file-based. There is no required
cloud infrastructure, queue, worker fleet, or distributed runtime in the
current operating model.

---

## System Flow

```text
Local CSV data
    ->
stock_analyzer
    ->
market_scanner
    ->
decision layer
    ->
backtest
```

Expanded view:

```text
stock_data_manager
  -> downloads and updates local OHLC CSVs

stock_analyzer
  -> generates current and historical per-symbol signals
  -> supports rsi-sma, lux, and smc

market_scanner
  -> evaluates many symbols
  -> builds Scanner V3 rows
  -> applies market_state, adjusted_alignment, action_bucket

backtest
  -> replays Scanner V3 historically
  -> measures signal quality, not options PnL

daily_report
  -> post-processes scan CSV + execution_recommended_rules.csv
  -> filters fresh signals (lux/smc days since event)
  -> ranks top candidates qualified by backtest
  -> renders actionable markdown report
```

---

## Main Modules

### `stock_data_manager`

Owns local market data ingestion and persistence.

- downloads historical OHLC data
- reads and writes local CSV files
- performs incremental updates

### `stock_analyzer`

Owns single-symbol signal generation.

- loads one symbol's OHLC data
- runs one signal model at a time
- exposes current and historical signals
- is the base signal engine used by the scanner

### `trading_indicators`

Owns low-level technical logic.

- indicator calculations
- Lux logic
- SMC logic

### `market_scanner`

Owns multi-symbol orchestration and decision logic.

- loads a universe
- filters eligibility
- builds scanner rows
- applies Scanner V3 decision fields
- exports ranked scanner outputs

See:

- `market-scanner.md`
- `market-scanner-decision-layer.md`
- `legacy-options-scanner.md`

### `ibkr_positions`

Owns live portfolio state and risk reporting.

- connects to IB Gateway via TWS API (read-only)
- fetches positions, account summary, cash balances
- computes unrealized P&L, margin utilization, cash coverage for short puts
- renders Markdown, CSV, and HTML reports with performance section

See `ibkr-positions.md`.

### Current Backtest

Owns Scanner V3 signal validation.

- replays scanner decisions bar by bar
- computes forward returns and directional metrics
- produces detailed and decision-oriented summaries

---

## Execution Model

The project currently runs as explicit local workflows:

- user runs a CLI or script
- local CSV data is loaded or updated
- analysis is computed synchronously
- results are printed or exported to CSV

This means:

- no async orchestration
- no distributed processing
- no always-on service requirement
- no message broker dependency

---

## Operating Sequence

The current operating sequence is:

```text
Data -> Analysis -> Decision -> Validation -> Daily Report
```

Meaning:

- `stock_data_manager` owns data
- `stock_analyzer` owns per-symbol analysis
- `market_scanner` owns multi-symbol decision
- the current backtest owns signal validation
- `daily_report` crosses fresh scanner signals with backtest-qualified setups

---

## Current Architectural Center

The most important shared artifact today is the Scanner V3 row.

`market_scanner.scanner_row` is the bridge between:

- per-symbol Lux/SMC analysis from `stock_analyzer`
- Scanner V3 decision logic
- scanner execution
- current backtest

This shared row is the current source of truth for multi-asset decision logic.

---

## Current Priorities

The project is no longer centered only on data download.

The current architecture should be understood in this order:

1. `stock_data_manager` keeps local data healthy
2. `stock_analyzer` produces reusable single-symbol signals
3. `market_scanner` turns those signals into scanner decisions
4. the current backtest validates whether those decisions have directional edge

---

## Non-Goals For The Current Stage

The current system is not trying to be:

- a real-time trading platform
- an event-driven microservice architecture
- a portfolio execution engine
- an options pricing or PnL engine
- an LLM-dependent decision system

If LLM features are added later, they should remain optional and explanatory,
not part of the deterministic decision engine.

The same applies to execution layers such as options strategy selection:

- they may consume scanner outputs
- they should not redefine the scanner decision engine

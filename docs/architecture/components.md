# Components

## Purpose

This document summarizes the main runtime components of the current local-first
system.

It focuses on responsibilities and collaboration between components, not on
file-by-file implementation detail.

---

## Data Components

### `stock_data_manager.StockDataManager`

Responsibilities:

- resolve file paths per symbol and interval
- load existing local CSV data
- download missing data
- merge old and new datasets
- persist final CSV results

Inputs:

- symbol list
- interval
- output directory
- merge strategy
- full refresh flag

Outputs:

- local CSV files
- pandas DataFrames

---

## Analysis Components

### `stock_analyzer.StockDataAnalyzer`

Responsibilities:

- select the active signal model
- orchestrate one-symbol analysis
- expose current signal output
- expose historical signal output

Inputs:

- one symbol
- one OHLC dataset
- selected model: `rsi-sma`, `lux`, or `smc`

Outputs:

- one current signal object
- one historical signal DataFrame

---

### `stock_analyzer.signals.lux.LuxSignalGenerator`

Responsibilities:

- adapt `trading_indicators.LuxSignalsOverlays`
- produce current Lux output
- produce historical Lux output

---

### `stock_analyzer.signals.smc.SMCSignalGenerator`

Responsibilities:

- adapt `trading_indicators.SmartMoneyConfluence`
- produce current SMC output
- produce historical SMC output

---

## Scanner Components

### `options_tech_scanner.scanner_row`

Responsibilities:

- build the shared Scanner V3 row
- normalize Lux and SMC outputs into one row
- derive decision inputs reused by scan and backtest

This is the current shared decision component of the scanner architecture.

---

### `options_tech_scanner.scan`

Responsibilities:

- load the scan universe
- validate eligibility
- build one scanner row per symbol
- export scanner reports

---

### Decision Layer

Owned by `options_tech_scanner` through:

- `ranking.py`
- `market_state.py`
- `scanner_row.py`

Responsibilities:

- alignment
- consistency score
- `market_state`
- `adjusted_alignment`
- `action_bucket`

---

## Backtest Components

### Current Backtest

Responsibilities:

- replay Scanner V3 historically
- compute forward metrics
- summarize directional signal quality
- export detailed and decision summaries

This component validates signal quality. It is not an options PnL engine.

---

## Supporting Components

### `trading_indicators`

Responsibilities:

- reusable indicator calculations
- Lux implementation logic
- SMC implementation logic

Rule:

- higher layers may compose its outputs, but should not duplicate its indicator
  logic.

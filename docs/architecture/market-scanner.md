# Market Scanner

## Purpose

`market_scanner` is the current multi-symbol orchestration and decision
layer of the project.

Its core question is:

**"Which assets are actionable now, and how should they be classified?"**

It is not the home of raw indicator calculations and it is not the raw market
data layer.

---

## Architectural Role

`market_scanner` sits above `stock_analyzer` and below reporting and
historical validation.

```text
local OHLC data
  ->
stock_analyzer
  ->
scanner row
  ->
current scanner decision layer
  ->
reports and backtest
```

---

## What It Owns

`market_scanner` owns:

- universe loading
- eligibility filtering
- multi-symbol orchestration
- shared analyzer orchestration for Lux and SMC
- shared scanner row construction
- current scanner decision logic
- scanner reporting
- signal-quality backtesting orchestration
- execution-capture backtesting orchestration

In practice, this includes:

- `alignment`
- `consistency_score`
- `market_state`
- `adjusted_alignment`
- `action_bucket`
- liquidity diagnostics such as `avg_volume_20` and `avg_dollar_volume_20`

Internally, the package is now organized around a small set of roles:

- `pipeline.py`
  - shared universe and symbol iteration orchestration
- `event_state.py`
  - Lux/SMC event extraction and ranking-mode state helpers
- `models.py`
  - shared scanner data models
- `scanner_row.py`
  - shared decision row assembly
- `scan.py`
  - current live scan orchestration
- `backtest.py`
  - historical replay and signal validation
- `backtest_execution.py`
  - trade-style execution capture validation
- `exits.py`
  - isolated execution exit rules
- `trades.py`
  - directional trade records and trade metrics

---

## What It Does Not Own

`market_scanner` should NOT own:

- raw OHLC data download
- low-level Lux implementation logic
- low-level SMC implementation logic
- single-symbol CLI analysis
- options PnL simulation

These belong elsewhere:

- data lifecycle -> `stock_data_manager`
- signal generation for one symbol -> `stock_analyzer`
- technical logic -> `trading_indicators`

Hard rule:

- `market_scanner` MUST NOT implement indicator logic.

---

## Current Decision Flow

The current scanner is no longer just a ranking pass over raw model outputs.

It is a decision layer built around the shared scanner row.

Decision flow:

```text
Lux + SMC outputs
  ->
alignment
  ->
market_state
  ->
adjusted_alignment
  ->
action_bucket
```

This means the scanner is responsible not only for finding symbols, but for
classifying their current state in a reusable, backtestable way.

---

## Current Scan Controls

The live scanner remains local-first and CSV-driven. Current scan controls
include:

- market-cap filtering
- 20-day average volume filtering
- 20-day average dollar-volume filtering through `--min-avg-dollar-volume-20`
- optional recent-window analysis through `--analysis-bars`
- scanner-oriented sorting through `--sort-by scanner`
- SMC recent-event sorting through `--sort-by smc-recent`

`analysis_bars` limits the data slice passed into the Lux/SMC analyzer for a
scan run. It is a scan-time analysis window, not a raw data download setting.

`smc-recent` sorting is a reporting/ranking view focused on recent SMC context.
It does not change the underlying Scanner V3 decision rules.

---

## Relationship With `stock_analyzer`

This is the most important boundary.

`stock_analyzer` answers:

- what does one asset signal now?
- what is the recent signal history for one symbol?

`market_scanner` answers:

- which symbols deserve attention now?
- which are candidates, watchlist setups, avoid cases, or unclear cases?

Rule of thumb:

- per-symbol interpretation -> `stock_analyzer`
- multi-symbol selection and decision -> `market_scanner`

---

## Relationship With The Current Backtest

The current backtest should consume scanner decisions, not reimplement them.

That is why the scanner row is shared between:

- live scan execution
- scanner reporting
- historical replay
- execution-capture replay

This is one of the most important architectural constraints in the current
system.

The scan and backtest now also share a pipeline layer for:

- universe loading
- optional symbol selection
- analyzer creation
- symbol-by-symbol local CSV iteration

---

## Relationship With Execution Backtest

`market_scanner.backtest_execution` is separate from
`market_scanner.backtest`.

The signal-quality backtest answers:

```text
Did the scanner decision have directional edge?
```

The execution backtest answers:

```text
How much of that edge was captured by a concrete entry/exit rule?
```

Execution backtest entries are still based on Scanner V3 decision rows:

- bullish entry: `action_bucket == candidate` and
  `adjusted_alignment == bullish_aligned`
- bearish entry: `action_bucket == candidate` and
  `adjusted_alignment == bearish_aligned`

Exit rules live in `exits.py` and remain isolated. The `--exit-rule all`
comparison mode runs the supported exit rules independently, then ranks the
results by directional execution metrics such as expectancy and profit factor.

This remains directional execution validation. It is not options PnL,
position sizing, slippage, commissions, or portfolio simulation.

---

## Current Assessment

`market_scanner` is currently the most architecturally sensitive part of
the project.

Why:

- it combines multiple upstream outputs
- it adds the project's main decision logic
- it owns the bridge between live scanning and historical validation

Because of that, it is also the package most likely to benefit from further
documentation review and selective refactoring.

`options_tech_scanner` still exists in the repository, but it should now be
read as:

- the legacy scanner package
- a compatibility namespace for migrated current-scanner modules

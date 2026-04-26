# Current Options Scanner

## Purpose

`options_tech_scanner` is the current multi-symbol orchestration and decision
layer of the project.

Its core question is:

**"Which assets are actionable now, and how should they be classified?"**

It is not the home of raw indicator calculations and it is not the raw market
data layer.

---

## Architectural Role

`options_tech_scanner` sits above `stock_analyzer` and below reporting and
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

`options_tech_scanner` owns:

- universe loading
- eligibility filtering
- multi-symbol orchestration
- shared scanner row construction
- current scanner decision logic
- scanner reporting
- signal-quality backtesting orchestration

In practice, this includes:

- `alignment`
- `consistency_score`
- `market_state`
- `adjusted_alignment`
- `action_bucket`

---

## What It Does Not Own

`options_tech_scanner` should NOT own:

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

- `options_tech_scanner` MUST NOT implement indicator logic.

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

## Relationship With `stock_analyzer`

This is the most important boundary.

`stock_analyzer` answers:

- what does one asset signal now?
- what is the recent signal history for one symbol?

`options_tech_scanner` answers:

- which symbols deserve attention now?
- which are candidates, watchlist setups, avoid cases, or unclear cases?

Rule of thumb:

- per-symbol interpretation -> `stock_analyzer`
- multi-symbol selection and decision -> `options_tech_scanner`

---

## Relationship With The Current Backtest

The current backtest should consume scanner decisions, not reimplement them.

That is why the scanner row is shared between:

- live scan execution
- scanner reporting
- historical replay

This is one of the most important architectural constraints in the current
system.

---

## Current Assessment

`options_tech_scanner` is currently the most architecturally sensitive part of
the project.

Why:

- it combines multiple upstream outputs
- it adds the project's main decision logic
- it owns the bridge between live scanning and historical validation

Because of that, it is also the package most likely to benefit from further
documentation review and selective refactoring.

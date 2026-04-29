# Backtest

## Purpose

The current scanner backtest is implemented in `market_scanner.backtest`.

The compatibility entrypoint `options_tech_scanner.backtest_v3` still exists
temporarily, but it should no longer be treated as the canonical module name.

The current backtest validates current scanner signal quality.

It does NOT simulate options trades or options PnL.
Trade-style execution capture validation lives separately in
`market_scanner.backtest_execution`.

Its core question is:

**"Did the current scanner signals have directional predictive value?"**

---

## Core Rule

No lookahead bias.

Each historical event must be built only from data available up to that bar.

Conceptually:

```text
for each symbol
  for each eligible bar
    build_scanner_row(history_up_to_bar)
    generate event
    compute forward metrics from later bars
```

---

## Inputs

The current backtest uses:

- local OHLC CSV data
- shared scanner pipeline orchestration
- shared current scanner row logic
- Lux and SMC historical signal outputs

It supports:

- `snapshot`
- `recent-event`
- `both`

It also supports local filtering:

- `--symbols`
- `--start-date`
- `--end-date`
- `--max-bars`

---

## Outputs

### Event-Level Output

Contains one historical scanner decision per symbol/bar/mode plus forward
metrics.

### Detailed Summary

Technical grouping for deeper inspection, including fields such as:

- `adjusted_alignment`
- `action_bucket`
- `market_state`
- `lux_strength`

### Decision Summary

Decision-oriented grouping focused on:

- `signal_side`
- `success_rate`
- `failure_rate`
- `avg_directional_return`
- `expectancy`

---

## Main Metrics

Fixed horizons:

- `3`
- `5`
- `10`
- `20`

For each horizon:

- forward return
- directional return
- MFE
- MAE
- success / failure
- expectancy

Important:

- bullish and bearish signals should be read through directional metrics
- `avg_return` alone is not the main decision metric for bearish cases

---

## Architectural Importance

The current backtest is valuable because it reuses the same scanner row logic
as the live scanner.

That means:

- one shared decision source
- less duplication
- better auditability

After the recent refactor, it also shares the same pipeline layer used by the
live scanner for:

- analyzer creation
- universe loading
- symbol iteration
- local dataset preparation

Rule:

- backtest should consume scanner decisions
- it should not redefine scanner logic independently

---

## Execution Backtest

`market_scanner.backtest_execution` is a separate downstream validation layer.

It simulates directional trades from Scanner V3 entries:

- bullish entries from `candidate` + `bullish_aligned`
- bearish entries from `candidate` + `bearish_aligned`

It supports isolated exit rules:

- `alignment_break`
- `bucket_downgrade`
- `late_state`
- `opposite_signal`
- `bars_5`
- `bars_10`
- `bars_20`

It also supports:

```text
--exit-rule all
```

That mode runs each exit rule independently, exports trades and summaries, and
adds `execution_rule_comparison.csv` with qualification and ranking fields.

Execution comparison metrics use directional returns and include:

- win rate
- loss rate
- average and median directional return
- expectancy
- profit factor
- MFE and MAE
- average holding period

This layer validates execution capture, not signal existence. It should not be
merged into `market_scanner.backtest`.

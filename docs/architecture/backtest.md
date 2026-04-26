# Backtest

## Purpose

The current backtest validates current scanner signal quality.

It does NOT simulate options trades or options PnL.

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

Rule:

- backtest should consume scanner decisions
- it should not redefine scanner logic independently

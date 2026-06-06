# Backtest Performance Plan

## Current State

`market_scanner.backtest` is already more optimized than the original suspicion
in the task suggested.

It does **not** recompute Lux and SMC from scratch for every historical bar.

Current flow per symbol after the first Phase 2 optimization:

1. generate `lux_historical` once
2. generate `smc_historical` once
3. resolve evaluation indexes after warmup/date/max-bars gating
4. for larger replays, precompute Lux/SMC event state once per symbol
5. iterate bar by bar
6. build scanner rows from current historical rows plus optional precomputed event state
7. compute forward metrics
8. summarize and export

The previous slow path remains available:

- if precomputed event state is not supplied,
  `build_scanner_row_from_history` still slices historical frames and computes
  state from history
- for small evaluation runs, the backtest intentionally skips precomputation
  because the setup cost can exceed the savings

## Measured Bottlenecks

Profiling confirmed that the main replay-loop bottleneck was repeated scanner
row construction from partial historical frames.

Measured on `AAPL --max-bars 100 --ranking-mode recent-event`:

Before event-state precompute:

- `build_scanner_row`: approximately `1.009s`
- `per_bar_loop`: approximately `1.117s`
- total measured time: approximately `5.504s`

After event-state precompute:

- `build_scanner_row`: approximately `0.030s`
- `per_bar_loop`: approximately `0.135s`
- `event_state_precompute`: approximately `0.859s`
- total measured time: approximately `4.779s`

Interpretation:

- the optimization was worthwhile because it removed the repeated per-bar
  scanner-row/event-state cost
- the total run improved moderately because the cost shifted to a one-time
  per-symbol precompute and other costs still remain
- the next bottleneck must be measured at larger scale before making another
  structural change

## Phase 1

Implemented in the current backtest:

- `--profile`
- warmup-safe `--start-date`
- `--end-date`
- `--max-bars`

Behavior:

- `start_date` filters emitted events, not warmup history
- `end_date` truncates the available dataset
- `max_bars` limits evaluated bars after warmup and date gating
- default behavior remains unchanged

## Phase 2

Partially implemented.

Implemented:

- `build_event_state_history`
  - precomputes `latest` and `active` event state per historical bar
  - preserves existing Lux/SMC active-event priority rules
- optional event-state inputs for `build_scanner_row_from_history`
  - keeps the old history-slice path as fallback/source-of-truth behavior
- backtest integration
  - uses event-state precompute only when the evaluation workload is large
    enough to justify it
  - keeps small `--max-bars` runs on the simpler path
- equivalence coverage
  - test compares a row built from historical slices with the same row built
    using precomputed event state

Current next step:

- profile a larger workload before refactoring further

Recommended command shape:

```bash
PYTHONPATH=src uv run python -m market_scanner.backtest \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --symbols AAPL,NVDA,MSFT,WFC,XOM \
  --max-bars 260 \
  --profile
```

Also profile:

- `--ranking-mode both`
- 5-10 symbols from the sample universe
- optionally a no-output or temp-output variant if CSV writing starts to distort
  measurements

Decision rule for the next optimization:

- if `event_state_precompute` dominates, optimize
  `build_event_state_history` first
- if `lux_historical_generation` or `smc_historical_generation` dominates,
  inspect the `stock_analyzer` adapters and underlying indicator generation
- if `summary_generation` dominates, optimize the pandas grouping/aggregation
- if `csv_writing` dominates, separate engine profiling from export profiling

Candidate future direction if smaller optimizations stop helping:

- build a historical scanner feature frame once per symbol
- keep the slow path as source of truth
- validate field-by-field equivalence before any engine switch

Do not start with the feature-frame rewrite in the next session unless profiling
shows the remaining bottleneck cannot be addressed locally.

## Guardrails

- no lookahead bias
- no duplicated scanner logic
- no indicator logic moved into `market_scanner`
- slow engine remains canonical until equivalence is proven
- current scanner row decision logic remains shared between scan and backtest

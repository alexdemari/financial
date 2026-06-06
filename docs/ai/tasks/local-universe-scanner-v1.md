# Task: Local Universe Scanner V1 (options_tech_scanner)

## Status

`DONE` on 2026-04-22.

Implemented:

- new local-only scanner flow in `options_tech_scanner.scan`
- local universe loading with `market_cap` / `market_cap_basic`
- eligibility filtering with explicit exclusion reasons
- Lux + SMC reuse via `stock_analyzer`
- V1 alignment and consistency scoring
- CSV export + top-N terminal summary
- automated tests for universe loading, eligibility, ranking, row generation, and sorting
- README documentation including CSV schema

Not implemented in this iteration:

- integration into `options_tech_scanner.main`
- async, cache, or parallel execution for the new flow
- confluence model
- network or update behavior inside the scanner

## Goal

Implement a local-first multi-asset scanner inside `options_tech_scanner` that:

1. scans a universe of assets using existing local data
2. applies Lux and SMC models per symbol
3. ranks assets based on signal consistency
4. generates:

   * a full CSV report
   * a top-N summary in terminal output

---

## Context

The project already has:

* `stock_data_manager` → maintains local OHLC CSV data
* `trading_indicators` → Lux, SMC, and technical primitives
* `stock_analyzer` → per-symbol analysis and adapters
* `options_tech_scanner` → existing scanner-oriented module (to be extended)

This task builds a **multi-symbol scanner**, not a single-symbol analyzer.

---

## Architectural Decision

This feature MUST live in `options_tech_scanner`.

Do NOT move it to `stock_analyzer`.

Reason:

* `stock_analyzer` = per-symbol analysis
* `options_tech_scanner` = multi-symbol scanning, ranking, and reporting

---

## Scope (V1 Only)

Implement a minimal, functional scanner with:

* local-only operation
* no network calls
* no async
* no event-driven architecture
* no ML or advanced ranking
* no confluence model yet

---

## CLI Interface

Suggested interface:

```bash
uv run python -m options_tech_scanner.scan \
  --universe-file data/us_symbols.json \
  --data-dir data/stocks/1D \
  --min-market-cap 1000000000 \
  --min-avg-volume-20 1000000 \
  --top 10 \
  --output reports/stock_analyzer/scan_latest.csv
```

Parameters:

* `--universe-file`: path to local universe metadata
* `--data-dir`: directory with OHLC CSVs
* `--min-market-cap`: eligibility filter
* `--min-avg-volume-20`: eligibility filter
* `--top`: number of rows printed to terminal
* `--output`: CSV output path

---

## Input Data

### Universe File

Must contain at least:

* `symbol`
* `market_cap` (or equivalent field like `market_cap_basic`)

### OHLC Data

CSV files located at:

```
data_dir/<INTERVAL>/<SYMBOL>.csv
```

Must contain:

* date
* open
* high
* low
* close
* volume

---

## Core Flow

For each symbol:

1. Load metadata from universe
2. Apply market cap filter
3. Attempt to load local CSV
4. Validate sufficient history
5. Compute `avg_volume_20`
6. Apply volume filter
7. Run Lux analysis
8. Run SMC analysis
9. Derive alignment
10. Compute consistency score
11. Build output row

---

## Eligibility Rules

A symbol is eligible if:

* `market_cap >= min_market_cap`
* CSV exists
* sufficient rows for analysis
* `avg_volume_20 >= min_avg_volume_20`

---

## Exclusion Reasons

Track explicitly:

* `market_cap_below_threshold`
* `missing_csv`
* `insufficient_history`
* `avg_volume_20_below_threshold`
* `analysis_failed`

---

## Average Volume Calculation

Compute:

* mean of `volume` over last 20 rows

Must:

* handle small datasets safely
* fail gracefully if insufficient rows

---

## Model Integration

Use existing modules:

* Lux via `stock_analyzer`
* SMC via `stock_analyzer`

Do NOT:

* reimplement Lux or SMC
* duplicate indicator logic

---

## Alignment Logic

Classify into:

* `bullish_aligned`
* `bearish_aligned`
* `mixed`
* `no_trade`

---

## Consistency Score (V1)

Simple rule-based scoring:

* +2 if `lux_options_hint == smc_options_hint` and both not `NO_TRADE`
* +1 if `lux_signal == smc_signal` and both not `HOLD`
* +1 if both directional (bullish or bearish)
* -1 if signals conflict

---

## Output CSV

Must include:

* symbol
* close
* avg_volume_20
* market_cap
* lux_signal
* lux_options_hint
* lux_context
* lux_trend
* lux_strength
* lux_adx
* smc_signal
* smc_options_hint
* smc_context
* smc_bias
* smc_range_position_pct
* smc_rsi
* alignment
* consistency_score

Optional (recommended):

* eligible
* excluded_reason

---

## Terminal Output

Print ONLY top-N rows.

Columns:

* symbol
* close
* avg_volume_20
* market_cap
* lux_options_hint
* smc_options_hint
* alignment
* consistency_score

---

## Internal Structure (Suggested)

```
options_tech_scanner/
  scan.py
  universe_loader.py
  eligibility.py
  ranking.py
  report_writer.py
```

---

## Responsibilities

Scanner MUST:

* orchestrate multi-symbol execution
* filter eligibility
* compute ranking
* generate outputs

Scanner MUST NOT:

* download data
* modify CSVs
* implement indicators
* handle async or infra

---

## Testing Requirements

Add tests for:

1. universe loading
2. market cap filtering
3. avg_volume_20 calculation
4. missing CSV handling
5. insufficient history handling
6. alignment classification
7. consistency score
8. CSV row generation
9. top-N sorting

Tests must:

* run without network
* use in-memory DataFrames
* mock boundaries only

---

## Documentation Requirements

Update or create docs explaining:

* scanner purpose
* CLI usage
* filters
* CSV output
* terminal output

---

## Constraints

Do NOT:

* move logic into `stock_analyzer`
* introduce async or Redis
* redesign architecture
* implement confluence yet
* overengineer ranking

---

## Output Instructions for Codex

1. Summarize current state of `options_tech_scanner`
2. Propose minimal implementation plan
3. List impacted files
4. Implement scanner V1
5. Add tests
6. Update docs
7. Summarize changes
8. List assumptions and limitations

---

## Definition of Done

The task is complete when:

* scanner runs end-to-end locally
* CSV is generated
* top-N is printed
* tests pass
* no network dependency exists
* architecture boundaries are preserved

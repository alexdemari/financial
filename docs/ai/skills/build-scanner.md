# Skill: Build Scanner (Multi-Asset)

## Goal

Implement a multi-asset scanner that:

* processes a universe of symbols
* applies eligibility filters
* runs models per symbol
* aggregates results
* ranks and classifies candidates
* outputs CSV plus a compact top-N terminal summary

The scanner must remain:

* local-first
* simple
* explicit
* testable

---

## Core Principle

A scanner answers:

> "Which assets deserve attention now?"

It is NOT responsible for:

* computing indicator internals
* downloading data
* single-asset analysis UX

---

## Architecture Rules

### Separation of Concerns

* `stock_data_manager` -> data storage and access
* `trading_indicators` -> model logic (Lux, SMC)
* `stock_analyzer` -> per-symbol analysis
* `market_scanner` -> orchestration, filtering, decision, ranking

---

### Do NOT

* duplicate Lux or SMC logic
* embed model logic inside scanner
* move scanner logic into `stock_analyzer`
* introduce async, queues, or infra
* over-abstract early

---

## Scanner Flow (Canonical)

For each symbol:

1. load universe metadata
2. apply eligibility filters
3. load local OHLC data
4. validate sufficient history
5. compute derived eligibility metrics such as `avg_volume_20`
6. run models through `stock_analyzer`
7. normalize outputs into a shared scanner row
8. compute `alignment` and `consistency_score`
9. classify `market_state`, `adjusted_alignment`, and `action_bucket`
10. build the final result row

---

## Two Critical Layers

### 1. Eligibility (Filter)

Determines if a symbol can be processed.

Examples:

* `market_cap >= threshold`
* `avg_volume_20 >= threshold`
* CSV exists
* enough history

Output:

* boolean eligibility
* explicit `excluded_reason`

---

### 2. Decision and Ranking

Determines priority among eligible symbols.

Must be:

* explicit
* deterministic
* simple

Avoid:

* implicit heuristics
* complex weighting
* ML or adaptive logic

For the current scanner, this includes:

* `alignment`
* `consistency_score`
* `market_state`
* `adjusted_alignment`
* `action_bucket`

---

## Output Contract

### CSV Output

Each row should include:

* symbol
* close
* avg_volume_20
* market_cap
* model outputs (Lux, SMC)
* `alignment`
* `consistency_score`
* `market_state`
* `adjusted_alignment`
* `action_bucket`

Optional but recommended:

* `eligible`
* `excluded_reason`

---

### Terminal Output

* show only top-N rows
* keep output compact and readable
* include key decision fields only

---

## Alignment Rules

Use a simple categorical classification:

* `bullish_aligned`
* `bearish_aligned`
* `mixed`
* `no_trade`

---

## Consistency Rules

Keep simple and explicit.

Example:

* `+2` -> same options hint (non `NO_TRADE`)
* `+1` -> same directional signal (non `HOLD`)
* `+1` -> both directional same side
* `-1` -> conflicting signals

---

## Data Rules

* operate only on local CSVs
* do not trigger downloads
* handle missing data explicitly
* skip invalid symbols with reason

---

## Error Handling

Never crash the entire scan due to one symbol.

Instead:

* skip symbol
* record `excluded_reason`
* continue processing

---

## Testing Strategy

Tests must cover:

* eligibility logic
* exclusion scenarios
* ranking logic
* market-state logic
* scanner row generation
* top-N sorting

Use:

* in-memory DataFrames
* local fixtures
* no network

---

## Implementation Strategy

### Step 1 - Plan

* define input/output
* define filters
* define decision fields
* define output schema

### Step 2 - Build Minimal Flow

* loop over symbols
* filter
* analyze
* collect rows

### Step 3 - Add Decision Layer

* compute alignment
* compute consistency
* classify state and action bucket

### Step 4 - Add Output

* CSV export
* terminal summary

---

## Anti-Patterns

Avoid:

* mixing eligibility and decision logic
* embedding model-specific logic in scanner core
* creating generic frameworks prematurely
* overengineering ranking logic
* adding infra (`Redis`, async workers, queues, etc.)

---

## Definition of Done

A scanner implementation is complete when:

* runs end-to-end locally
* produces CSV output
* prints top-N summary
* handles missing data safely
* has test coverage for core logic
* respects architecture boundaries
* shares the same row logic between live scan and backtest when applicable

---

## Summary

A good scanner:

* is simple
* is deterministic
* is explicit
* is built on top of existing modules
* produces actionable output

For the current project, that means:

* `market_scanner` consumes per-symbol signals from `stock_analyzer`
* it must not duplicate Lux or SMC internals
* live scan and backtest should share the same scanner row logic

It should evolve gradually, not be overdesigned upfront.

# market_scanner

Multi-symbol orchestration and Scanner V3 decision engine.

## Responsibility

- Loads universe from CSV
- Filters eligibility (market cap, volume, history)
- Calls `stock_analyzer` per symbol
- Builds Scanner V3 rows via `scanner_row`
- Applies `market_state`, `adjusted_alignment`, `action_bucket`
- Exports ranked CSV output
- Owns signal-quality backtest

## Hard rules — never violate

- MUST NOT implement Lux or SMC indicator logic
- MUST NOT call `stock_data_manager` download functions
- Scanner row must be defined in `market_scanner.scanner_row` — reused by both live scan and backtest

## Scanner V3 fields

`lux_role` → `smc_role` → `alignment` → `market_state` → `adjusted_alignment` → `action_bucket`

Values for `action_bucket`: `candidate`, `watchlist`, `avoid`, `needs_review`

## Error handling

Never crash the full scan for one symbol.
Catch per-symbol errors, record `excluded_reason`, continue.

## Backtest rule

Backtest consumes scanner row decisions — it does NOT reimplement them.
If you change `scanner_row`, both live scan and backtest outputs change.

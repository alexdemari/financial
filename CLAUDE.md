# financial

Local-first Python project for market data management and signal analysis.

## Stack

- Python 3.11+, pandas, uv
- CSV-based persistence (no DB, no ORM)
- pytest for tests

See @README.md for commands.
See @docs/architecture/overview.md for architecture.
See @docs/architecture/module-boundaries.md for module rules.

## Run & Test

```bash
uv run pytest
uv run ruff check src tests
PYTHONPATH=src uv run python -m <module>.main
```

Always run from repo root. Always use `PYTHONPATH=src`.

## Module Boundaries — Hard Rules

- `market_scanner` MUST NOT implement indicator logic (Lux, SMC)
- `stock_analyzer` answers single-symbol questions only
- `trading_indicators` owns all raw technical calculations
- `stock_data_manager` is the data layer — never triggers analysis
- Scanner decision logic must be defined once in `market_scanner.scanner_row`

## What NOT to introduce

- Redis, queues, async, distributed systems
- External databases (Postgres, etc.)
- Event buses or streaming
- Refactors of unrelated modules

## Things to get right

- `PYTHONPATH=src` is required — never omit it
- Tests must not hit network — mock `yfinance` at `stock_data_manager.downloader.yf`
- DataFrames for OHLC must have at least 50 bars (SMC requires history)
- CSV date index must be parsed as DatetimeIndex, not string
- Do not duplicate Lux or SMC logic — reuse `trading_indicators`
- Scanner row fields: `lux_role`, `smc_role`, `alignment`, `market_state`, `adjusted_alignment`, `action_bucket`

## Git (WSL)

```bash
wsl bash -lc "cd /mnt/c/Users/alexa/Documents/development/financial && git commit -m '...'"
```

If ruff-format rewrites files during commit: re-stage and re-run the wsl commit command.

## Compaction

When compacting, always preserve:
- list of modified files
- current test status
- any unresolved issues or open decisions

# AGENTS.md

Local-first Python project for financial market data analysis and signal generation.

## Quick orientation

See @README.md for all CLI commands.
See @docs/architecture/overview.md for architecture.
See @docs/architecture/module-boundaries.md for module ownership rules.
See @docs/ai/context-map.md for file-to-module mapping.

## Test & lint (always run after changes)

```bash
uv run pytest
uv run ruff check src tests
```

Run targeted tests when scope is clear:

```bash
uv run pytest tests/stock_analyzer
uv run pytest tests/market_scanner
```

Always prefix with `PYTHONPATH=src` when running modules directly:

```bash
PYTHONPATH=src uv run python -m stock_analyzer.main -s AAPL --model lux --local-only
```

## Hard constraints — never violate

- `market_scanner` MUST NOT implement indicator logic (Lux, SMC) — those belong in `trading_indicators`
- `stock_analyzer` answers single-symbol questions only — never universe scanning
- `stock_data_manager` is the data layer — analysis modules never trigger downloads
- Scanner row fields must come from `market_scanner.scanner_row`, not be reimplemented elsewhere
- No Redis, async, queues, distributed systems, or external databases

## What to get right

- Tests must not hit network — mock `yfinance` at `stock_data_manager.downloader.yf`
- DataFrames for OHLC must use `DatetimeIndex`, never string index
- Minimum 50 bars required for SMC calculations
- Do not duplicate Lux or SMC logic — always reuse `trading_indicators`

## Git (WSL only)

```bash
wsl bash -lc "cd /mnt/c/Users/alexa/Documents/development/financial && git commit -m '...'"
```

If ruff-format rewrites files during commit: re-stage and re-run.

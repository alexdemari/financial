# AGENTS.md

## Project Context

This is a Python financial tooling project with a modular structure under `src/`.

Current main modules:

- `stock_data_manager`
- `stock_analyzer`
- `options_tech_scanner`
- `ibkr`

`stock_data_manager` is currently a synchronous, batch-oriented module using:

- CLI execution
- `StockDataManager` as the orchestrator
- `yfinance` for historical market data downloads
- CSV persistence
- pandas DataFrames
- append and update merge strategies

It is not currently event-driven.

## Environment

The project is normally run from PyCharm Terminal using Ubuntu/WSL.

Prefer running commands from WSL/Ubuntu:

```bash
uv run pytest
.venv/bin/python -m pytest tests/stock_data_manager
just --list
```

PowerShell can be used for file inspection and edits, but Python, `uv`, and pre-commit may fail there because the virtualenv and Git hooks are WSL-oriented.

## Documentation

Architecture docs live under:

```text
docs/arquitecture
```

Note: the directory name is currently misspelled as `arquitecture`.

Treat event-driven architecture docs and ADRs as future-facing unless matching implementation exists.

## Testing

For `stock_data_manager`, run:

```bash
.venv/bin/python -m pytest tests/stock_data_manager
```

Tests should avoid network calls. Use fakes or mocks for provider behavior such as `yfinance`.

## Git Safety

The working tree may contain unrelated staged and unstaged changes.

Before committing:

- inspect `git status --short`
- stage only files related to the current task
- use path-scoped commits when needed
- do not revert unrelated changes

If pre-commit fails from PowerShell because it cannot find the WSL virtualenv, rerun from Ubuntu/WSL when possible. For docs-only or already verified changes, `--no-verify` may be acceptable if the reason is documented in the final response.

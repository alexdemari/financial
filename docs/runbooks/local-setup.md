# Local Setup

## Purpose

Prepare a local development environment for the project.

This project is:

- local-first
- CLI-driven
- file-based
- synchronous

It does not require cloud infrastructure, queues, databases, or external
services to run its core workflows.

---

## Requirements

Install:

- Python
- `uv`
- Git
- WSL/Ubuntu if you are working from Windows

You also need local market data in CSV form under the project's data
directories when running scanner and analyzer flows in local-only mode.

---

## Recommended Environment

Preferred environment:

- WSL/Ubuntu

Reason:

- Python tooling, `uv`, virtual environments, and Git hooks are more reliable
  in this repository when run from WSL than from native PowerShell.

PowerShell is still fine for:

- file inspection
- editing
- light repository navigation

---

## Initial Setup

From the repository root:

```bash
uv sync --dev
```

This installs development dependencies and prepares the local virtual
environment.

---

## Local Data Expectations

Core workflows expect local CSV data such as:

```text
data/stocks/1D/<SYMBOL>.csv
```

Examples:

- `data/stocks/1D/AAPL.csv`
- `data/stocks/1D/NVDA.csv`

The scanner also expects a local universe file, for example:

- `data/scanner_universe_sample.csv`

---

## Basic Validation

Validate the environment with targeted tests:

```bash
.venv/bin/python -m pytest tests/stock_data_manager
.venv/bin/python -m pytest tests/stock_analyzer
.venv/bin/python -m pytest tests/market_scanner
```

You can also run lint:

```bash
.venv/bin/python -m ruff check src tests
```

---

## Basic Usage Checks

Single-symbol analysis:

```bash
PYTHONPATH=src uv run python -m stock_analyzer.main -s AAPL --model lux --local-only
```

Current market scanner:

```bash
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output reports/market_scanner/scan.csv
```

Current backtest:

```bash
PYTHONPATH=src uv run python -m market_scanner.backtest \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --symbols AAPL \
  --max-bars 260
```

---

## Windows Notes

If you are on Windows:

- prefer running Python tooling from WSL
- prefer running commits from WSL
- avoid mixing Windows and WSL virtualenv workflows unless necessary

This repository has already shown environment friction when `uv` manipulates
the same `.venv` from both sides.

---

## Troubleshooting

If setup looks broken:

1. confirm you are running from the repository root
2. confirm `.venv` exists after `uv sync --dev`
3. confirm local CSV data exists for the symbols you are testing
4. prefer rerunning the command from WSL if PowerShell behaves differently

If scanner or backtest commands fail on missing files, verify:

- symbol CSV exists
- universe file exists
- paths are relative to the repo root

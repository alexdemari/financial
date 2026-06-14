# Project Conventions (canonical)

This file is the source of truth for any AI coding agent working on this repo (Claude Code, Codex CLI, etc.). Tool-specific extensions live in `CLAUDE.md` (slash commands, sub-agents, hooks). Personal/local overrides live in `CLAUDE.local.md` (gitignored).

## Environment

- Development happens on WSL / Ubuntu (Windows host). All shell commands assume `bash` on WSL.
- Python is managed by `uv`; the venv is `.venv` inside the repo. **Always invoke Python tools via `uv run <cmd>`** (`uv run pytest`, `uv run ruff`, `uv run python -m ...`). Never call `pytest` or `python` bare — they may resolve to a system interpreter.
- Editors: PyCharm / Cursor from Windows side. The agent does not need to interact with the editor; just edit files.

## Planning & Communication

- When proposing a plan, **list the files to be modified first**, then describe changes per file. Don't describe before listing.
- After implementing a change, **show the exact test command** that validates it (e.g. `uv run pytest tests/backtest/test_filters.py -k test_min_price -x -q`).
- Prefer **explicit, descriptive variable names** over brevity (`min_price_threshold` over `mp`).

## Behavioral Constraints

1. Don't assume. Don't hide confusion. Surface tradeoffs.
2. Minimum code that solves the problem. Nothing speculative.
3. Touch only what you must. Clean up only your own mess.
4. Define success criteria. Loop until verified.

## Testing

- Always run the full test suite after refactors, especially parallelization or changes to function signatures (analyzers, workers, etc.). Use `uv run pytest -x -q`.
- Verify bit-identical output when optimizing existing code paths. Use the project's `verify-identical` recipe.
- When `workers=1` or any sequential mode exists, preserve the original code path to avoid regressions.
- Prefer `-x -q` flags to fail fast during iteration.

### Hard rules
- No network — mock `yfinance` at `stock_data_manager.downloader.yf`
- No real CSV reads — build DataFrames in memory
- Mock only external boundaries, not internal functions
- Test behavior, not implementation details

### Canonical OHLC fixture

```python
import pandas as pd
import numpy as np

def make_ohlcv(n: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = 100.0 + np.cumsum(np.random.randn(n))
    return pd.DataFrame({
        "Open":   close * 0.99,
        "High":   close * 1.01,
        "Low":    close * 0.98,
        "Close":  close,
        "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
    }, index=dates)
```

Index must be `DatetimeIndex`. Minimum 50 bars for SMC; 100 recommended. Columns capitalized.

```python
@patch("stock_data_manager.downloader.yf.download")
def test_something(mock_dl):
    mock_dl.return_value = make_ohlcv(200)
```

Coverage minimum per module: happy path, empty DataFrame, insufficient bars (< 50), missing columns.

## Code Style (Python)

- Type hints on all public functions and methods.
- Prefer pure functions; isolate I/O at module boundaries.
- Explicit variable names — see Planning section.

## Commit Practices

- Commit messages: imperative mood, conventional-commit-ish prefix: `feat:`, `fix:`, `refactor:`, `perf:`, `docs:`, `test:`, `chore:`.
- Body explains *why*, not *what*. The diff already shows what.
- After completing a feature or refactor, update relevant docs (justfile, README, etc.) and commit/push as a final step unless told otherwise.

## Domain — Backtest Engine

- **Bit-identical output is a hard contract** for any refactor that does not explicitly change semantics. If you change semantics deliberately, say so in the commit body.
- Treat the SQLite cache as **write-once-read-many**. Never mutate cached rows in-place; invalidate and rewrite instead.
- Temporal split logic must respect the `embargo` parameter; do not leak future data into training windows.
- Performance work must report before/after timings and confirm bit-identical (or document the deliberate divergence).

## Sub-Agents & Parallelism (general)

- When delegating to parallel sub-agents, dispatch them in a **single batch** (one tool-call turn) so the prefix cache is shared.
- The orchestrator must verify sub-agent work (run tests, read changes) before declaring tasks complete.
- Run integration tests after fan-out completes and before any commit.

## Dividend Tracker Domain Rules

Non-negotiable rules for any session touching `dividend_tracker` or
`config/dividend_portfolio.yaml`.

### avg_6y must exclude the current year

`calculate_average_annual_dividend` MUST filter out the current calendar year
before computing the average. Partial-year data systematically understates
the dividend base.

```python
current_year = date.today().year
hist_complete = hist[hist.index.year < current_year]
```

### BR assets: yfinance includes JCP

For Brazilian tickers (`.SA` suffix), `yfinance` returns dividends AND JCP
(Juros sobre Capital Próprio) in the same `ticker.dividends` series. No
separate adjustment or filtering is needed. This is the intended behavior.

### ceiling_method rationale

`trailing` for assets with rapid dividend growth (>50% in 5 years) or linear
ETFs — avg_6y would understate current capacity.

`average_6y` for assets with irregular annual distributions (typical for BR
regulated sectors) — smooths extraordinary and weak years.

### min_dy reflects structural DY, not aspirational targets

Set min_dy to the asset's historical average DY range. If 6% global default
would permanently mark an asset as OVERPRICED (it has never reached 6% DY),
reduce min_dy to match structural range.

Current calibrated values: see `config/dividend_portfolio.yaml` (authoritative)
and `docs/architecture/dividend-tracker.md` (reference table).

### TAEE11 replaced EGIE3 on 2026-06-11 — do not revert

TAEE11 (pure transmission, ANEEL-guaranteed revenue) replaced EGIE3 (generation)
due to materially higher DY (7.7% vs 3.6%) with equal or lower risk profile.
See `docs/ai/tasks/dividend-tracker-calibration.md` for full rationale.

### No technical analysis in dividend decision

`dividend_tracker` does NOT call `stock_analyzer`. The decision is purely
fundamental: `price <= price_ceiling → BUY`, otherwise `OVERPRICED`.

10-year backtests confirmed no proportional gain from technical models for
this strategy. Do not re-introduce `technical_model`, `technical_models`,
`timeframe`, or `conviction_multiplier` fields into the decision flow.
These YAML fields are silently ignored for backwards compatibility only.

### PEP is monitored, not contributed

`target_weight: 0.0` means PEP appears in the report for monitoring but
receives no budget allocation. It is operated via cash-secured put selling
on IBKR. Do not change target_weight without explicit instruction.

## What NOT to do

- Do not re-read large files you've already read in this session unless they may have changed.
- Do not improvise long shell command sequences when a `just` recipe exists for it. If a recipe is missing, propose adding it instead of hardcoding the sequence.
- Do not push directly to `main` without an explicit instruction.
- Do not edit `.venv/`, `bench/history.jsonl`, or `tests/baselines/` unless the task explicitly requires it.

## Compliance & Safety (non-negotiable)
- Never log or expose raw financial data / PII in outputs or tests.
- Temporal split logic must respect `embargo`; leaking future data into training windows is a silent correctness bug with no test signal.

## Strategy & Filter Plumbing
- When adding or modifying strategy-specific logic, trace the `strategy`
  parameter end-to-end (signal generation → filter → ranking → report)
  before implementing — never assume it propagates automatically
- Symbol-level recommendations must not be silently dropped by filters
  defaulting to `'none'`

## Justfile Conventions
- Before creating or editing a recipe, run the target CLI with `--help`
  and verify the actual flag names — do not assume them
- New scan/report recipes must align output paths with downstream
  consumers (e.g., `daily-report` expects scanner output at a specific path)
- `just` does not support named flags in recipe arguments; use positional
  args or environment variables

## Data Access

- One CSV per symbol: `data/stocks/1D/<SYMBOL>.csv` or `data/stocks/1W/<SYMBOL>.csv`
- Access via `stock_data_manager` functions — never read CSVs directly in other modules
- No database, no ORM, no network in analysis flows

```python
# Correct
from stock_data_manager.loader import load_symbol_csv
df = load_symbol_csv(data_dir, symbol)

# Wrong — never in stock_analyzer or market_scanner
df = pd.read_csv(f"data/stocks/1D/{symbol}.csv")
```

CSV date column must always be parsed as `DatetimeIndex` (`index_col=0, parse_dates=True`). String index causes silent wrong indicator results.

`stock_analyzer` and `market_scanner` must operate on local data only — no `yfinance` calls.

## Scanner Architecture

Module responsibility — never cross these boundaries:

```
trading_indicators  →  raw Lux/SMC calculations
stock_analyzer      →  per-symbol signal (lux_role, smc_role)
market_scanner      →  alignment, market_state, action_bucket
```

### Canonical scanner row fields

| Field | Type | Values |
|---|---|---|
| `lux_role` | str | Lux context role for current bar |
| `smc_role` | str | SMC context role for current bar |
| `alignment` | str | `bullish_aligned`, `bearish_aligned`, `mixed`, `no_trade` |
| `consistency_score` | int | numeric score combining signal agreement |
| `market_state` | str | `pullback`, `range`, `extended` |
| `adjusted_alignment` | str | decision-aware alignment after context |
| `action_bucket` | str | `candidate`, `watchlist`, `avoid`, `needs_review` |

All fields must come from `market_scanner.scanner_row`. Never reimplement in other modules.

### Eligibility vs Decision — never mix

**Eligibility** (filter before processing): CSV exists, `market_cap >= threshold`, `avg_volume_20 >= threshold` → boolean + `excluded_reason`.

**Decision** (rank eligible symbols): `alignment` → `market_state` → `adjusted_alignment` → `action_bucket`. Must be deterministic.

### Error handling in scanner

Never crash full scan for one symbol:

```python
try:
    row = build_scanner_row(symbol, df)
    results.append(row)
except Exception as e:
    results.append({"symbol": symbol, "eligible": False, "excluded_reason": str(e)})
```

Live scan and backtest share the same `build_scanner_row` — changing it changes both. Intentional.

## On-Demand Context Files

Pass explicitly via `--context` when task requires it:

- `.codex/skills/reviewing-code.md` — code review checklist + output format
- `.codex/skills/validating-backtest.md` — backtest hard rules + review checklist
- `.codex/skills/writing-tests.md` — full test coverage matrix + file naming

## Definition of Done
A feature is only complete when:
- Full test suite is passing — report N/N count explicitly
- Any new justfile recipe has been verified against `--help` output
- Output paths confirmed against downstream consumers
- Docs and runbook updated if behavior changed

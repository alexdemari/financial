---
name: reviewing-code
description: >
  Reviews code changes for correctness, architecture compliance, test quality,
  and documentation drift in this project. Use when reviewing a diff, recent
  commit, pull request, or specific files after implementation. Also use when
  asked to check module boundaries, test coverage, stats correctness, or
  label accuracy in reports.
---

# Reviewing Code

## What to check

### 1. Module boundaries — hard rules

- `market_scanner` must not contain Lux/SMC indicator logic → MUST FIX
- `stock_analyzer` must not do multi-symbol work → MUST FIX
- Analysis modules must not call `yfinance` directly → MUST FIX
- Scanner row fields must come from `market_scanner.scanner_row` → MUST FIX
- `daily_report.py` is post-processing only — must not run scanner or download data

### 2. Stats and labels — correctness

- Counts shown in report sections must reflect what actually happened
- "Qualificados pelo backtest" only when recommendations filter was applied
- Pre-cap count (before `.head(N)`) and post-cap count (in top-N) must be tracked separately
- Labels must change when optional inputs are absent (e.g. `--recommendations` not passed)

### 3. Tests

- No network access — `yfinance` must be mocked at `stock_data_manager.downloader.yf`
- DataFrames built in memory — no real CSV reads in tests
- Tests validate behavior, not just that functions were called
- Edge cases covered: empty DataFrame, None values, missing columns, below-threshold inputs
- Helper fixtures (`_make_scan_row`, `_make_rec_row`) must reflect real column names

### 4. Defensive data handling

- Columns with optional values (days, events) handled via `.notna()` before comparison
- `None` values in join keys (e.g. `symbol=None` in global recommendations) filtered before set construction
- Missing columns in DataFrames handled gracefully — use `.get()` or column existence checks

### 5. Scope

- Changes outside the stated task scope flagged as unintended
- Unrelated modules not modified

### 6. Documentation drift

- If a new entry point was added, check `docs/ai/context-map.md` for stale references
- If CLI behavior changed, check `README.md` Common Commands section
- If module boundary changed, check `docs/architecture/module-boundaries.md`

## Output format

```
MUST FIX:
- <specific issue, file and line if possible>

SHOULD FIX:
- <issue that matters but won't break immediately>

CONSIDER:
- <optional improvement or doc drift noticed>

SAFE:
- <confirmed correct sections>
```

Be specific. Financial data — correctness matters.

## After fixes

```bash
uv run pytest tests/market_scanner/ -v
uv run ruff check src/market_scanner/ tests/market_scanner/
```

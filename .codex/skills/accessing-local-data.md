---
name: accessing-local-data
description: >
  Handles local CSV data access patterns for OHLC market data. Use when
  loading or saving symbol data, working with stock_data_manager, implementing
  data access in any module, or when questions involve DatetimeIndex,
  CSV files under data/stocks/1D/, or the data layer boundary.
---

# Accessing Local Data

## Data layout

```
data/stocks/1D/<SYMBOL>.csv   ← one file per symbol
```

## Loading — always use the data manager

```python
# Correct
from stock_data_manager.loader import load_symbol_csv
df = load_symbol_csv(data_dir, symbol)

# Wrong — never do this in stock_analyzer or market_scanner
df = pd.read_csv(f"data/stocks/1D/{symbol}.csv")
```

## DatetimeIndex rule

CSV date index must always be parsed as `DatetimeIndex`:

```python
df = pd.read_csv(path, index_col=0, parse_dates=True)
# df.index is DatetimeIndex — not strings
```

Strings silently break all indicator calculations.

## Analysis must not trigger downloads

`stock_analyzer` and `market_scanner` operate on local data only.
Use `--local-only` flag. Never call `yf.download()` from analysis modules.

## Future SQLite layer

Planned in `docs/ai/tasks/introduce-sqlite-data-layer.md` — not active.
Do not implement unless that task is explicitly in scope.
CSV remains default when implemented.

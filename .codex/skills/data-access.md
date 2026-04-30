# Skill: Data Access Patterns

Rules for reading and writing data in this project.

---

## Current Data Layer

- One CSV per symbol under `data/stocks/1D/<SYMBOL>.csv` or `data/stocks/1W/<SYMBOL>.csv`
- Access via `stock_data_manager` functions — never read CSVs directly in other modules
- No database, no ORM, no network in analysis flows

---

## Loading Data

```python
# Correct — use the data manager
from stock_data_manager.loader import load_symbol_csv
df = load_symbol_csv(data_dir, symbol)

# Wrong — never do this in stock_analyzer or market_scanner
df = pd.read_csv(f"data/stocks/1D/{symbol}.csv")
```

---

## DatetimeIndex Rule

CSV date column must always be parsed as DatetimeIndex:

```python
df = pd.read_csv(path, index_col=0, parse_dates=True)
assert isinstance(df.index, pd.DatetimeIndex)
```

Never leave the index as strings — indicators will silently produce wrong results.

---

## Analysis Must Not Trigger Downloads

`stock_analyzer` and `market_scanner` must operate on local data only.

```python
# Wrong — analysis modules must not download
import yfinance as yf
df = yf.download(symbol)

# Correct — use --local-only flag and pre-downloaded CSVs
df = load_symbol_csv(data_dir, symbol)
```

The `--local-only` flag exists for this reason.

---

## Future: SQLite Layer (planned, not active)

A `PriceDataRepository` interface is planned (`docs/ai/tasks/introduce-sqlite-data-layer.md`).
Do not implement it unless that task is explicitly in scope.
When implemented, CSV remains default — SQLite is opt-in.

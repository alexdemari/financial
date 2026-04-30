# Task: Introduce SQLite Data Layer

**Status:** Planned
**Skill:** adding-features
**Scope:** `src/stock_data_manager/` only

---

## Goal

Add opt-in SQLite support to `stock_data_manager` without breaking the existing CSV workflow.

---

## Outcome spec

When done, the following must be true:

1. `load_symbol_csv()` continues to work exactly as today — no behavior change
2. A `SqlitePriceDataRepository` exists and loads the same data as CSV for the same symbol
3. An importer script migrates CSV → SQLite: `python -m stock_data_manager.importers.csv_to_sqlite --data-dir data/stocks/1D --db-path data/financial.db`
4. Tests pass: `uv run pytest tests/stock_data_manager`
5. No changes to `stock_analyzer`, `market_scanner`, or `trading_indicators`
6. No external DB dependencies — use `sqlite3` (stdlib only)

---

## Constraints

- CSV remains the default — SQLite is opt-in
- No async, no ORM, no Postgres
- No changes outside `stock_data_manager`
- `PRIMARY KEY(symbol, date)` — no duplicate rows

---

## Key design

```
PriceDataRepository (base)
    ├── CsvPriceDataRepository   ← wraps existing load_symbol_csv()
    └── SqlitePriceDataRepository ← new, sqlite3 only
```

Files to create:
```
src/stock_data_manager/repositories/base.py
src/stock_data_manager/repositories/csv_repository.py
src/stock_data_manager/repositories/sqlite_repository.py
src/stock_data_manager/importers/csv_to_sqlite.py
src/stock_data_manager/schema/sqlite_schema.sql
```

---

## SQLite schema

```sql
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY(symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date ON ohlcv_daily(symbol, date);
```

---

## Verification

```bash
# Migrate one symbol
python -m stock_data_manager.importers.csv_to_sqlite \
  --data-dir data/stocks/1D --db-path /tmp/test.db --symbols AAPL

# Load via SQLite repo and compare to CSV
python -c "
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository
repo = SqlitePriceDataRepository('/tmp/test.db')
df = repo.load_symbol('AAPL')
print(df.shape, df.index.dtype)
"

uv run pytest tests/stock_data_manager
```

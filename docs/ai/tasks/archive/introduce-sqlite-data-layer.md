# Task: Introduce SQLite Data Layer (PriceDataRepository)

## Context

The system currently stores OHLC data as:

- one CSV file per symbol
- accessed via load_symbol_csv()

This works, but has limitations:

- inefficient for large datasets
- hard to query by date ranges
- fragile for consistency
- slows down backtest iteration
- no metadata tracking

We want to introduce a **local SQLite data layer** while preserving current behavior.

---

## Goal

Add a new data access layer using SQLite, without breaking existing CSV-based workflow.

The system must:

- support both CSV and SQLite
- keep CSV as default
- allow gradual migration
- remain local-first and deterministic

---

## Constraints

DO NOT:

- remove CSV support
- introduce external databases (Postgres, etc.)
- introduce async or services
- modify scanner behavior
- modify stock_analyzer logic

DO:

- keep changes isolated to stock_data_manager
- design minimal abstraction
- ensure compatibility with existing code

---

## High-Level Design

Introduce a repository pattern:

~~~text
PriceDataRepository (interface)
    ├── CsvPriceDataRepository
    └── SqlitePriceDataRepository
~~~

The rest of the system should depend only on the interface.

---

## Directory Structure

Create:

~~~text
src/stock_data_manager/
  repositories/
    base.py
    csv_repository.py
    sqlite_repository.py
  importers/
    csv_to_sqlite.py
  schema/
    sqlite_schema.sql
~~~

---

## 1. Base Interface

File:

src/stock_data_manager/repositories/base.py

Define:

~~~python
class PriceDataRepository:
    def load_symbol(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        raise NotImplementedError

    def list_symbols(self) -> list[str]:
        raise NotImplementedError
~~~

---

## 2. CSV Repository

File:

src/stock_data_manager/repositories/csv_repository.py

Responsibilities:

- wrap existing load_symbol_csv()
- maintain current behavior
- no logic change

Example:

~~~python
class CsvPriceDataRepository(PriceDataRepository):
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def load_symbol(self, symbol: str) -> pd.DataFrame:
        return load_symbol_csv(self.data_dir, symbol)

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        path = Path(self.data_dir) / f"{symbol}.csv"
        df.to_csv(path, index=True)

    def list_symbols(self) -> list[str]:
        return [...]
~~~

---

## 3. SQLite Schema

File:

src/stock_data_manager/schema/sqlite_schema.sql

~~~sql
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    dividends REAL,
    stock_splits REAL,
    source TEXT,
    imported_at TEXT,
    PRIMARY KEY(symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date
ON ohlcv_daily(symbol, date);

CREATE INDEX IF NOT EXISTS idx_ohlcv_date
ON ohlcv_daily(date);
~~~

---

## 4. SQLite Repository

File:

src/stock_data_manager/repositories/sqlite_repository.py

Requirements:

- use sqlite3 (stdlib)
- no ORM
- simple queries only

Example structure:

~~~python
class SqlitePriceDataRepository(PriceDataRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def load_symbol(self, symbol: str) -> pd.DataFrame:
        query = """
        SELECT *
        FROM ohlcv_daily
        WHERE symbol = ?
        ORDER BY date
        """
        return pd.read_sql_query(query, self._connect(), params=[symbol])

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        # insert or replace rows
        ...

    def list_symbols(self) -> list[str]:
        ...
~~~

---

## 5. CSV → SQLite Importer

File:

src/stock_data_manager/importers/csv_to_sqlite.py

Responsibilities:

- iterate CSV directory
- load each symbol
- insert into SQLite

CLI-style usage:

~~~bash
python -m stock_data_manager.importers.csv_to_sqlite \
  --data-dir data/stocks/1D \
  --db-path data/financial.db
~~~

---

## 6. Data Consistency Rules

- PRIMARY KEY(symbol, date) prevents duplicates
- use INSERT OR REPLACE
- dates must be ISO format
- DataFrame index must map to date

---

## 7. Integration (Non-breaking)

DO NOT replace existing calls yet.

Add optional usage:

~~~python
repo = SqlitePriceDataRepository("data/financial.db")
df = repo.load_symbol("AAPL")
~~~

Existing:

~~~python
df = load_symbol_csv(...)
~~~

must continue working.

---

## 8. Optional CLI Integration (future-ready)

Add flags (do not enforce yet):

~~~bash
--data-source csv
--data-source sqlite
--db-path data/financial.db
~~~

---

## 9. Tests

Create:

tests/stock_data_manager/test_sqlite_repository.py

Test:

1. Insert and load symbol
2. No duplicate rows
3. Order by date is correct
4. CSV vs SQLite equivalence

---

## 10. Acceptance Criteria

- CSV workflow unchanged
- SQLite repository loads same data as CSV
- Importer populates database correctly
- Tests pass (pytest)
- No changes required in scanner or analyzer

---

## Success Definition

The system can:

- run fully on CSV (current behavior)
- run on SQLite without code changes elsewhere
- switch between sources safely

---

## Final Principle

~~~text
Introduce abstraction without changing behavior.
Migration must be additive, not disruptive.
~~~

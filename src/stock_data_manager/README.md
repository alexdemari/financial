# Stock Data Manager

`stock_data_manager` is a local, batch-oriented Python module for downloading and maintaining historical stock market data.

It uses:

- `yfinance` for historical market data
- pandas DataFrames for in-memory processing
- CSV files for default local persistence
- optional SQLite persistence for local experiments and repeated reads
- interface-based components for reader, writer, downloader, and merge behavior
- `StockDataManager` as the workflow orchestrator

The module is designed for local historical data workflows. It is not a real-time ingestion service and does not currently use events, queues, workers, or Redis.

## Responsibilities

- Download historical stock data for one or more symbols.
- Reuse existing CSV files when available.
- Perform incremental updates by downloading only missing data.
- Force full refreshes when requested.
- Merge existing and newly downloaded data.
- Persist the final dataset as CSV by default.
- Optionally persist the final dataset in a local SQLite database.
- Support CLI and programmatic usage.

## Architecture

```text
CLI / Python caller
  -> StockDataManager
      -> CSVReader | SQLiteReader
      -> YFinanceDownloader
      -> AppendMergeStrategy | UpdateMergeStrategy
      -> CSVWriter | SQLiteWriter
```

Key design choices:

- `StockDataManager` coordinates the workflow.
- `IDataReader`, `IDataWriter`, `IDataDownloader`, and `IMergeStrategy` isolate responsibilities.
- `CSVReader` and `CSVWriter` implement the default local file persistence.
- `SQLiteReader` and `SQLiteWriter` implement opt-in local SQLite persistence.
- `YFinanceDownloader` fetches data from Yahoo Finance through `yfinance`.
- `AppendMergeStrategy` and `UpdateMergeStrategy` define merge behavior.
- `StockDataManagerFactory` wires the default concrete dependencies.

SQLite is currently an opt-in data-manager backend. CSV remains the default and
canonical workflow for scanner and backtest compatibility.

## Requirements

- Python 3.13 or newer, as configured in `pyproject.toml`
- `uv` for dependency management
- `just` is optional, but useful for common project commands

Install dependencies from the repository root:

```bash
uv sync --dev
```

## CLI Usage

Run commands from the repository root.

With the current project layout, set `PYTHONPATH=src` and run the package module:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL MSFT
```

### Download Specific Symbols

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL MSFT GOOGL
```

Brazilian tickers must include the Yahoo Finance suffix:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s PETR4.SA VALE3.SA
```

### Download From A File

Text file:

```txt
AAPL
MSFT
GOOGL
PETR4.SA
```

Command:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -f symbols.txt
```

CSV files are also supported. The loader looks for common columns such as `symbol`, `ticker`, `Symbol`, or `Ticker`. If none is found, it uses the first column.

### Download TradingView Tickers

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -a data/data.json -i 1d
```

### Force A Full Refresh

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL --full
```

### Select Merge Strategy

Default append strategy:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL --strategy append
```

Update strategy:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL --strategy update
```

### Select Interval

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL -i 1d
```

Current downloader interval mapping:

```python
{
    "1d": "1D",
    "1w": "1wk",
    "1m": "1mo",
}
```

The CLI validates the interval against this supported set.

### Output Directory

By default, the CLI writes files under:

```text
data/stocks/{INTERVAL}
```

For example:

```text
data/stocks/1D/AAPL.csv
```

Use `--data-dir` to override the output directory:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL -d ./custom-data
```

### Use SQLite Storage

SQLite support is local-first and experimental. It is useful when testing a
single database file as the data-manager persistence layer, but scanner and
backtest workflows still read local CSV files unless they are adapted
separately.

CSV remains the default:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main -s AAPL --storage csv
```

Write and read through SQLite:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.main \
  -s AAPL MSFT \
  --storage sqlite \
  --db-path data/financial.db
```

The SQLite backend stores rows in `ohlcv_daily` using `(symbol, date)` as the
primary key. Re-running the same symbol replaces rows for matching dates rather
than duplicating them.

### Import Existing CSV Data Into SQLite

Use the importer when you already have CSV files under `data/stocks/1D`:

```bash
PYTHONPATH=src uv run python -m stock_data_manager.importers.csv_to_sqlite \
  --data-dir data/stocks/1D \
  --db-path data/financial.db
```

Programmatic read:

```python
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository

repo = SqlitePriceDataRepository("data/financial.db")
df = repo.load_symbol("AAPL")
symbols = repo.list_symbols()
```

## Just Commands

The project `justfile` includes helper commands such as:

```bash
just download AAPL
just download-br
just download-us
just download-from-file symbols.txt
```

Use `just --list` from the repository root to see the available commands.

## Programmatic Usage

```python
from stock_data_manager.factories import StockDataManagerFactory

manager = StockDataManagerFactory.create_default(
    data_dir="data/stocks/1D",
)

data = manager.download_and_save("AAPL", interval="1d")
print(data.tail())

results = manager.download_multiple(["MSFT", "GOOGL"], interval="1d")
```

Use the update merge strategy:

```python
from stock_data_manager.factories import StockDataManagerFactory

manager = StockDataManagerFactory.create_with_update_strategy(
    data_dir="data/stocks/1D",
)
```

## Data Format

CSV files are written with the DataFrame index as the first column.

Typical columns returned by `yfinance` include:

```csv
Date,Open,High,Low,Close,Volume,Dividends,Stock Splits
2024-01-02,185.64,186.95,184.15,185.63,54153800,0.0,0.0
2024-01-03,184.35,185.40,183.43,184.25,58414400,0.0,0.0
```

## Extension Points

The module is designed to be extended through interfaces.

Possible extensions:

- Add another `IDataDownloader` for a different provider.
- Add another `IDataReader` and `IDataWriter` for Parquet, DuckDB, or another local format.
- Add another `IMergeStrategy` for stricter merge behavior.
- Add retry logic around provider failures.
- Add manager-level interval validation for programmatic usage before calling the downloader.

## Known Limitations

- Execution is synchronous and sequential.
- CSV persistence is not suitable for concurrent writes.
- The read, merge, and write sequence is not transactional.
- SQLite persistence is opt-in and not yet the default scanner/backtest input.
- Failed downloads are logged but not retried automatically.
- Data freshness depends on manual execution or external scheduling.
- `yfinance` is not a guaranteed real-time market data source.

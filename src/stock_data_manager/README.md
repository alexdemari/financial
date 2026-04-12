# Stock Data Manager

`stock_data_manager` is a local, batch-oriented Python module for downloading and maintaining historical stock market data.

It uses:

- `yfinance` for historical market data
- pandas DataFrames for in-memory processing
- CSV files for local persistence
- interface-based components for reader, writer, downloader, and merge behavior
- `StockDataManager` as the workflow orchestrator

The module is designed for local historical data workflows. It is not a real-time ingestion service and does not currently use events, queues, workers, or Redis.

## Responsibilities

- Download historical stock data for one or more symbols.
- Reuse existing CSV files when available.
- Perform incremental updates by downloading only missing data.
- Force full refreshes when requested.
- Merge existing and newly downloaded data.
- Persist the final dataset as CSV.
- Support CLI and programmatic usage.

## Architecture

```text
CLI / Python caller
  -> StockDataManager
      -> CSVReader
      -> YFinanceDownloader
      -> AppendMergeStrategy | UpdateMergeStrategy
      -> CSVWriter
```

Key design choices:

- `StockDataManager` coordinates the workflow.
- `IDataReader`, `IDataWriter`, `IDataDownloader`, and `IMergeStrategy` isolate responsibilities.
- `CSVReader` and `CSVWriter` implement local file persistence.
- `YFinanceDownloader` fetches data from Yahoo Finance through `yfinance`.
- `AppendMergeStrategy` and `UpdateMergeStrategy` define merge behavior.
- `StockDataManagerFactory` wires the default concrete dependencies.

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

With the current project layout, use one of these forms:

```bash
uv run python -m src.stock_data_manager.main -s AAPL MSFT
```

or set `PYTHONPATH=src` and run:

```bash
uv run python -m stock_data_manager.main -s AAPL MSFT
```

### Download Specific Symbols

```bash
uv run python -m src.stock_data_manager.main -s AAPL MSFT GOOGL
```

Brazilian tickers must include the Yahoo Finance suffix:

```bash
uv run python -m src.stock_data_manager.main -s PETR4.SA VALE3.SA
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
uv run python -m src.stock_data_manager.main -f symbols.txt
```

CSV files are also supported. The loader looks for common columns such as `symbol`, `ticker`, `Symbol`, or `Ticker`. If none is found, it uses the first column.

### Download TradingView Tickers

```bash
uv run python -m src.stock_data_manager.main -a data/data.json -i 1d
```

### Force A Full Refresh

```bash
uv run python -m src.stock_data_manager.main -s AAPL --full
```

### Select Merge Strategy

Default append strategy:

```bash
uv run python -m src.stock_data_manager.main -s AAPL --strategy append
```

Update strategy:

```bash
uv run python -m src.stock_data_manager.main -s AAPL --strategy update
```

### Select Interval

```bash
uv run python -m src.stock_data_manager.main -s AAPL -i 1d
```

Current downloader interval mapping:

```python
{
    "1d": "1D",
    "1w": "1wk",
    "1m": "1mo",
}
```

Note: the CLI help currently mentions `1h`, but `YFinanceDownloader` does not map `1h` yet.

### Output Directory Caveat

The CLI accepts `--data-dir`, but the current CLI flow derives the active output directory from the project path and selected interval:

```text
data/stocks/{INTERVAL}
```

For example:

```text
data/stocks/1D/AAPL.csv
```

Programmatic usage can still pass a custom `data_dir` to `StockDataManagerFactory`.

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
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

manager = StockDataManagerFactory.create_default(
    data_dir="data/stocks/1D",
)

data = manager.download_and_save("AAPL", interval="1d")
print(data.tail())

results = manager.download_multiple(["MSFT", "GOOGL"], interval="1d")
```

Use the update merge strategy:

```python
from stock_data_manager.factories.manager_factory import StockDataManagerFactory

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
- Add another `IDataReader` and `IDataWriter` for Parquet, SQLite, DuckDB, or another local format.
- Add another `IMergeStrategy` for stricter merge behavior.
- Add retry logic around provider failures.
- Add interval validation before calling the downloader.

## Known Limitations

- Execution is synchronous and sequential.
- CSV persistence is not suitable for concurrent writes.
- The read, merge, and write sequence is not transactional.
- Failed downloads are logged but not retried automatically.
- Data freshness depends on manual execution or external scheduling.
- `yfinance` is not a guaranteed real-time market data source.
- The CLI `--data-dir` option is currently not used as the active output directory.

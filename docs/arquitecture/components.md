# Components - Stock Data Manager

## StockDataManager

### Responsibilities

- Resolve file paths per symbol
- Load existing data, if present
- Calculate incremental download range
- Execute data download
- Merge datasets using the selected strategy
- Persist the final dataset
- Return DataFrame results

---

### Inputs

- Symbols
- Interval
- Merge strategy
- Force full flag
- Output directory

Note: the current CLI parses an output directory argument, but the active output path is derived from the project path and selected interval.

---

### Outputs

- CSV files
- pandas DataFrames

---

## Downloader (`YFinanceDownloader`)

### Responsibilities

- Fetch historical data from `yfinance`
- Return provider data as a pandas DataFrame

### Dependency

- `yfinance`

---

## Reader (`CSVReader`)

### Responsibilities

- Load CSV files into DataFrames
- Handle missing or invalid files

---

## Writer (`CSVWriter`)

### Responsibilities

- Persist DataFrames to CSV
- Ensure directory structure exists

---

## Merge Strategies

### Responsibilities

- Define how datasets are combined
- Ensure consistency and deduplication

---

## Factory (`StockDataManagerFactory`)

### Responsibilities

- Configure default dependencies
- Provide predefined configurations

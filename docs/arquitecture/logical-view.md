# Logical View - Stock Data Manager

## Overview

The module is composed of loosely coupled components connected through interfaces.

---

## Main Components

### CLI

- Entry point for batch execution
- Parses user input and options
- Triggers `StockDataManager` workflows

---

### StockDataManager

Core orchestrator responsible for:

- Managing the data lifecycle per symbol
- Coordinating read -> download -> merge -> write
- Handling incremental logic

---

### Downloader (`YFinanceDownloader`)

- Fetches historical data from Yahoo Finance
- Returns pandas DataFrame

---

### Reader (`CSVReader`)

- Loads existing data from CSV files
- Converts CSV -> DataFrame

---

### Writer (`CSVWriter`)

- Persists DataFrame to CSV
- Ensures directory creation

---

### Merge Strategy

Defines how existing and new data are combined.

#### AppendMergeStrategy

- Appends new data
- Removes duplicates

#### UpdateMergeStrategy

- Updates existing rows
- Appends missing data

---

### Factory (`StockDataManagerFactory`)

- Assembles dependencies
- Injects reader, writer, downloader, and strategy

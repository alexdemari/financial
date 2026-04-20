# Architecture Overview - Stock Data Manager

## Purpose

The `stock_data_manager` module is responsible for:

- Downloading historical market data for financial assets
- Persisting data locally (CSV)
- Supporting incremental updates to avoid redundant downloads

It acts as the **data ingestion and persistence layer** of the system.

---

## Scope

This module currently supports:

- Batch execution via CLI or programmatic usage
- Historical data ingestion using external providers (`yfinance`)
- Local file-based storage (CSV)

---

## Out of Scope

- Real-time data ingestion
- Event-driven processing
- Financial analysis or signal generation
- Options scanning or strategy evaluation

These responsibilities belong to other modules:

- `stock_analyzer`
- `options_tech_scanner`

---

## Architectural Style

- Modular monolith
- Orchestrated workflow (`StockDataManager`)
- Interface-driven design (SOLID principles)
- Strategy pattern for merge logic
- Factory pattern for dependency injection

---

## Execution Model

The system operates in a **synchronous, batch-oriented workflow**:

```text
CLI -> StockDataManager -> Downloader -> Merge -> CSV
```

Execution is:

- Sequential
- Blocking
- Triggered by user command or script

---

## Key Limitations

- No real-time or continuous processing
- No event-based decoupling
- No concurrency or parallel execution
- File-based persistence limits scalability

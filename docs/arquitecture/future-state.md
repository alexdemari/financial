# Future State - Stock Data Manager

## Status

This document describes possible future evolution. It does not describe the current implementation.

The current `stock_data_manager` module is a synchronous, CLI-driven, CSV-backed batch data manager.

## Near-Term Improvements

The following improvements fit the current architecture without changing the execution model:

- Add validation for supported intervals before calling `YFinanceDownloader`.
- Make the CLI `--data-dir` option control the actual output directory.
- Add retry logic for transient provider failures.
- Add tests for incremental date calculation.
- Add tests for append and update merge behavior.
- Add tests for CLI symbol loading.
- Add a persistence implementation for Parquet, SQLite, or DuckDB behind the existing reader and writer interfaces.

## Possible Event-Driven Evolution

Event-driven processing is not implemented today.

If it becomes necessary, the safest migration path is to keep the existing abstractions and introduce an orchestration wrapper around them:

```text
event handler
  -> StockDataManager
  -> CSVReader / YFinanceDownloader / MergeStrategy / CSVWriter
```

For local-first development, the first event transport should be either:

- an in-memory event bus for single-process execution and tests
- Redis for lightweight local multi-process execution

Any future event-driven design should keep clear boundaries between what exists today and what is planned.

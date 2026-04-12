# Event Model - Stock Data Manager

## Current State

`stock_data_manager` does not currently implement an event-driven architecture.

Execution is:

- Synchronous.
- CLI-driven or programmatically invoked.
- Sequential for multiple symbols.
- In-process only.

There is no event bus, Redis integration, queue, worker process, or durable event log in the current module.

## Current Workflow Signals

The implementation has workflow steps that could become events in the future, but they are currently plain method calls and log messages.

Current logical steps:

- A download is requested by the CLI or a Python caller.
- Existing local data is read from CSV.
- A download range is calculated.
- Data is requested from `yfinance`.
- Existing and new rows are merged.
- The final DataFrame is written to CSV.
- Per-symbol success or failure is reported by the CLI.

These are not event contracts.

## Current Limitations

Because there is no implemented event model:

- Components are not coordinated asynchronously.
- There are no published or consumed event types.
- There is no event replay.
- There is no subscriber model.
- There is no durable queue for failed work.
- Failures are logged and represented in return values, not emitted as events.

## Future Direction

Event-driven processing is a possible future evolution only.

If introduced later, event handling should wrap the existing `StockDataManager` workflow instead of replacing the reader, writer, downloader, and merge strategy abstractions immediately.

Potential future event names could include:

- `stock.data.requested`
- `stock.data.updated`
- `stock.data.failed`

These events are not implemented today.

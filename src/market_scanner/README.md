# Market Scanner

`market_scanner` is the current multi-symbol scanner package.

It sits on top of:

- `stock_data_manager` for local CSV data
- `stock_analyzer` for per-symbol Lux and SMC signals

Its job is to:

- load a local universe
- apply eligibility filters
- orchestrate Lux and SMC analyzers across many symbols
- build a shared scanner row
- classify assets with `market_state`, `adjusted_alignment`, and `action_bucket`
- validate signal quality historically through `market_scanner.backtest`

Internal shape:

- `pipeline.py`
  - shared universe/analyzer/symbol iteration flow
- `event_state.py`
  - event extraction and ranking-mode helpers
- `models.py`
  - shared scanner models
- `scanner_row.py`
  - shared decision row assembly
- `scan.py`
  - current scan entrypoint
- `backtest.py`
  - current backtest entrypoint

Main entrypoints:

- `market_scanner.scan`
- `market_scanner.backtest`

`options_tech_scanner` remains in the repository for the legacy scanner and
temporary compatibility imports.

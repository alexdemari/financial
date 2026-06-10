# Dividend Tracker

## Purpose

`dividend_tracker` evaluates a user-defined dividend portfolio by combining
fundamental dividend yield thresholds with the existing single-symbol technical
signals from `stock_analyzer`.

Its core question is:

**"Which dividend assets are inside their price ceiling and technically worth
buying or watching today?"**

---

## Architectural Role

`dividend_tracker` is a consumer of local OHLC data and single-symbol technical
analysis. It does not replace the scanner decision layer.

```text
config/dividend_portfolio.yaml
  ->
dividend_tracker
  -> yfinance dividend cache in data/dividends/
  -> stock_analyzer technical signal
  ->
reports/dividend_tracker/dividend_daily_report.md
```

Expanded flow:

```text
portfolio config
  ->
dividend_data
  ->
price_ceiling
  ->
stock_analyzer
  ->
decision
  ->
report
```

---

## Responsibilities

`dividend_tracker` owns:

- loading and validating the dividend portfolio YAML
- adding `.SA` for Brazilian tickers when fetching Yahoo Finance dividend data
- caching dividend data in `data/dividends/` with a 24-hour TTL
- calculating dividend price ceiling from trailing twelve-month dividends or
  six-year average annual dividends
- combining price ceiling state with a technical signal
- generating the dividend daily markdown report
- optional budget allocation across `BUY` and `WATCH` assets

---

## What It Does NOT Own

`dividend_tracker` should NOT own:

- OHLC download and CSV lifecycle
- Lux, SMC, or RSI/SMA indicator logic
- broad market scanner ranking
- Scanner V3 fields such as `alignment`, `market_state`, or `action_bucket`
- brokerage execution

Those belong to:

- data lifecycle -> `stock_data_manager`
- single-symbol technical signals -> `stock_analyzer`
- low-level indicators -> `trading_indicators`
- multi-symbol scanner decisions -> `market_scanner`

---

## Key Types

### `DividendPortfolioConfig`

Parsed representation of `config/dividend_portfolio.yaml`.

Includes:

- `settings`
- `br_assets`
- `us_assets`

### `DividendAssetConfig`

Per-asset portfolio entry.

Includes:

- `ticker`
- `sector`
- `name`
- `target_weight`
- `technical_model`
- `market`
- optional `min_dy` override
- optional `ceiling_method` override (`trailing` or `average_6y`)
- optional `notes` for monitored assets

### `DividendData`

Cached dividend and price snapshot.

Includes:

- current price
- trailing annual dividends
- trailing dividend yield
- distribution history

### `PriceCeilingResult`

Fundamental price-ceiling result.

Includes:

- price ceiling
- current dividend yield
- trailing annual dividends
- dividend base used in the numerator
- ceiling method used for the numerator
- current price
- margin to ceiling

### `AssetDecision`

Final dividend contribution decision.

Values:

- `BUY`
- `WATCH`
- `WAIT`
- `OVERPRICED`

---

## CLI Interface

```bash
PYTHONPATH=src uv run python -m dividend_tracker.main \
  --config config/dividend_portfolio.yaml \
  --data-dir data/stocks \
  --budget 8000 \
  --output reports/dividend_tracker/dividend_daily_report.md
```

Use local cached dividend data and local OHLC CSVs only:

```bash
PYTHONPATH=src uv run python -m dividend_tracker.main --local-only
```

Recipes:

```bash
just dividends budget=8000
just dividends-local budget=8000
```

---

## Integration Points

- Reads portfolio config from `config/dividend_portfolio.yaml`
- Reads and writes dividend cache under `data/dividends/`
- Calls `stock_analyzer.StockDataAnalyzer` directly for technical signals
- Reads OHLC through `stock_analyzer`, which delegates local data access to
  `stock_data_manager`
- Writes report to `reports/dividend_tracker/dividend_daily_report.md`

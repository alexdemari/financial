# Dividend Tracker

## Purpose

`dividend_tracker` evaluates a user-defined dividend portfolio against
fundamental dividend yield thresholds.

Its core question is:

**"Which dividend assets are currently trading below their price ceiling
(DY >= min_dy) and therefore candidates for contribution today?"**

---

## Architectural Role

`dividend_tracker` is a consumer of yfinance dividend data. It does not depend
on `stock_analyzer` and does not perform technical analysis.

```text
config/dividend_portfolio.yaml
  ->
dividend_tracker
  -> yfinance dividend cache in data/dividends/
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
decision (BUY / OVERPRICED)
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
- generating the dividend daily markdown report
- optional budget allocation across `BUY` assets

---

## What It Does NOT Own

`dividend_tracker` should NOT own:

- OHLC download and CSV lifecycle
- Lux, SMC, or RSI/SMA indicator logic
- broad market scanner ranking
- Scanner V3 fields such as `alignment`, `market_state`, or `action_bucket`
- technical analysis of any kind
- calls to `stock_analyzer` for signal generation
- brokerage execution

`ConvictionLevel`, `technical_models`, and `timeframe` config fields are
silently ignored if present in YAML for backwards compatibility.

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

- `settings` — `DividendSettings` (global thresholds and behavior flags)
- `br_assets`
- `us_assets`

### `DividendSettings`

Portfolio-level configuration.

Includes:

- `min_dy` — minimum dividend yield threshold (default 6%)
- `dy_source` — dividend base method (`trailing`, `forward`, `average_6y`)
- `currency_br` / `currency_us` — display currency labels

### `DividendAssetConfig`

Per-asset portfolio entry.

Includes:

- `ticker`
- `sector`
- `name`
- `target_weight`
- `market`
- optional `min_dy` override
- optional `ceiling_method` override (`trailing` or `average_6y`)
- optional `notes` for monitored assets

Legacy YAML fields `technical_model`, `technical_models`, `timeframe`, and
`conviction_multiplier` are silently ignored when loading config.

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

- `BUY` — price <= price_ceiling (DY >= min_dy)
- `OVERPRICED` — price > price_ceiling (DY < min_dy)

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

## Price Ceiling Logic

```
price_ceiling = dividend_base(ceiling_method) / effective_min_dy
```

Where:

- `dividend_base`
  - `trailing` -> TTM dividends (last 12 months)
  - `average_6y` -> arithmetic mean of annual dividends over the last 6
    complete calendar years; years with no payment within the window count as zero
- `effective_min_dy`
  - `asset.min_dy` if set in YAML for the asset
  - `settings.min_dy` otherwise

`average_6y` follows the AGF methodology to smooth irregular distributions.
Brazilian assets may have years with high JCP, extraordinary dividends, or
weak payments; using TTM alone can over- or under-estimate the sustainable
dividend.

### average_6y: current year exclusion

`calculate_average_annual_dividend` MUST exclude the current (incomplete)
calendar year from the six-year average. Including a partial year pulls the
average down systematically.

```python
current_year = date.today().year
hist_complete = hist[hist.index.year < current_year]
```

Example: running in June 2026, the average uses 2020–2025 (six complete years).
2026 data is excluded regardless of how many months have elapsed.

### Asset reference table

| Asset  | ceiling_method | min_dy | Rationale |
|--------|----------------|--------|-----------|
| TAEE11 | average_6y     | 6.0%   | Replaced EGIE3 (2026-06-11). Pure transmission model, ANEEL-guaranteed revenue. Historical DY 6–9%. avg_6y R$3.56, TTM DY 8.41%. |
| ITSA4  | trailing       | 6.0%   | avg_6y distorted by 14× dividend growth (R$0.12 in 2020 → R$1.72 in 2025). TTM (DY 9.81%) is the representative figure. |
| BBSE3  | average_6y     | 6.0%   | Consistent historical DY 6–12%. avg_6y adequate; no distortion. |
| VIVT3  | trailing       | 6.0%   | avg_6y penalises recent dividend growth. TTM R$2.42 (DY 7.27%) already exceeds 6% criterion. |
| SAPR4  | average_6y     | 4.5%   | Structural DY 4–5%, never 6% historically. avg_6y correct after excluding current incomplete year. |
| SCHD   | trailing       | 3.4%   | Historical average DY. Above average = relatively cheap vs own history. |
| DGRO   | trailing       | 2.8%   | Historical average DY. |
| VYM    | trailing       | 3.0%   | Historical average DY. |
| PEP    | trailing       | 3.8%   | Dividend King 54y. US market prices 2.5–4.5% structurally. Monitored via put selling. |

This table is a snapshot — `config/dividend_portfolio.yaml` is authoritative.

---

## Decision Logic

Price ceiling only — no technical analysis:

```
BUY        → current_price <= price_ceiling  (DY >= min_dy)
OVERPRICED → current_price > price_ceiling   (DY < min_dy)
```

### Why no technical analysis

10-year backtests (1D and 1W timeframes, 2016–2026) across all portfolio
assets showed technical models added complexity without proportional gain:

- `lux` 1D: 10–15 signals/year, 25–40% precision at 45 days
- `smc` 1D: 0.4–0.8 signals/year, 37–57% precision (too infrequent for
  monthly contributions)
- `rsi-sma`: zero signals over 10 years on all assets

The price ceiling based on minimum DY already captures the essential
valuation filter. Disciplined DCA below the ceiling outperforms attempted
technical timing for long-horizon dividend portfolios.

See `reports/backtest/` for full results.

### Backtest tool (analysis only, not operational)

`just backtest-dividends` runs historical analysis of technical models for
reference purposes. It does not influence the daily decision.

Evaluation windows:

- **45 days** — percentage of BUY signals with gain >= 5%
- **90 days** — same criterion over a larger window
- **Combined signals** — model BUY AND price <= price_ceiling

### Last backtest results

- Daily (1D): `reports/backtest/dividend_entry_points_10y.md`
- Weekly (1W): `reports/backtest/dividend_entry_points_10y_weekly.md`

Weekly backtest uses 9-week (primary) and 18-week (secondary) windows,
counted in bars — not calendar days.

Last run: 2026-06-10

---

## Monitored assets (`target_weight = 0.0`)

Assets with `target_weight: 0.0` are analysed and appear in the daily report,
but are excluded from the contribution guide. This pattern is used for assets
operated via options strategies, where entry occurs through option exercise
rather than direct contribution.

Currently monitored:

- PEP — operated via recurring cash-secured put selling on IBKR

---

## Integration Points

- Reads portfolio config from `config/dividend_portfolio.yaml`
- Reads and writes dividend cache under `data/dividends/`
- Does NOT call `stock_analyzer` — no technical signal dependency
- Writes report to `reports/dividend_tracker/dividend_daily_report.md`

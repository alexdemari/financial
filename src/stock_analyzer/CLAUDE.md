# stock_analyzer

Single-symbol signal generation engine.

## Responsibility

- Loads one symbol's OHLC data
- Runs one model at a time: `rsi-sma`, `lux`, `smc`
- Returns current signal and optionally historical signals
- Used as the base signal engine by `market_scanner`

## Does NOT own

- Universe scanning or multi-symbol logic
- Scanner V3 decision fields (`market_state`, `action_bucket`, etc.)
- Data download — use `--local-only` or pre-downloaded CSVs

## Key contracts

- Input: `pd.DataFrame` with `DatetimeIndex`, columns `Open High Low Close Volume`
- Minimum bars: 50 (SMC); 100 recommended
- Output signal fields: `signal` (`BUY`/`SELL`/`HOLD`), `lux_role`, `smc_role`

## What to get right here

- Model selection is via `--model` flag — do not hardcode
- `--local-only` must skip any download attempt
- Historical mode returns one row per bar — not just the last signal

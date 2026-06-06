We are starting a new session on the `financial` project.

Before doing anything else, read these files first:

- `README.md`
- `docs/architecture/overview.md`
- `docs/architecture/module-boundaries.md`
- `docs/architecture/stock-analyzer.md`
- `docs/architecture/market-scanner.md`
- `docs/architecture/market-scanner-decision-layer.md`
- `docs/architecture/legacy-options-scanner.md`
- `docs/architecture/backtest.md`

Use this architecture as the default mental model:

- `stock_data_manager`
  - local-first data acquisition and CSV lifecycle
- `stock_analyzer`
  - single-symbol signal engine
  - generates `BUY` / `SELL` / `HOLD` plus Lux/SMC context
- `market_scanner`
  - current multi-symbol decision engine
  - classifies symbols with `market_state`, `adjusted_alignment`, and `action_bucket`
- `options_tech_scanner`
  - legacy scanner package
  - may contain compatibility shims for migrated modules
- `market_scanner.backtest`
  - validates signal quality
  - does NOT simulate options PnL

Important operating assumptions:

- the project is local-first
- scanner and backtest operate on local CSV data
- `market_scanner` must not implement raw indicator logic
- `stock_analyzer` is the source of per-symbol Lux/SMC signals
- `market_scanner` is the place for multi-symbol filtering and decision
- the legacy options scanner should not absorb new generic scanner logic

Important scanner terminology:

- `lux_role`
  - Lux context role for the current bar
- `smc_role`
  - SMC context role for the current bar
- `alignment`
  - raw directional relationship between Lux and SMC roles
- `market_state`
  - structural context such as `pullback`, `range`, `extended`
- `adjusted_alignment`
  - decision-aware interpretation after context adjustment
- `action_bucket`
  - `candidate`, `watchlist`, `avoid`, or `needs_review`

At the start of the session:

1. Summarize the current architecture in 5-10 lines.
2. Confirm which module or workflow is the focus of the task.
3. List any constraints or invariants that should not be broken.
4. Do NOT make code changes until the current state is understood.

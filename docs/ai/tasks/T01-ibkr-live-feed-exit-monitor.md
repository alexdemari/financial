# Task: Wire Live IBKR Positions into `exit_monitor`

**Status:** Completed
**Skill:** add-feature
**Scope:** `src/ibkr_positions/`, `src/market_scanner/exit_monitor.py`, `justfile`
**Effort:** M
**Depends on:** `just ibkr-positions` (already working)

---

## Context

`ibkr_positions` already fetches live portfolio state and writes a dated HTML/CSV/MD
report under `reports/output/`. The exit_monitor (`just positions`) reads a manually
maintained `options_tracker.csv` to detect DTE thresholds and exit signals.

The gap: the live account data never feeds the exit monitor automatically. Any
position opened or closed on IBKR requires a manual edit to `options_tracker.csv`
before the exit monitor reflects it.

Current account (2026-06-23) has 4 short options expiring 2026-07-17 (24 DTE):
- AAPL 260717C00310000 (covered call)
- FSLY 260717P00015000 (short put, ×5)
- PEP  260717P00140000 (cash-secured put)
- SMR  260717P00009000 (short put, ×12 — at −34% unrealized loss)

---

## Goal

After running `just ibkr-positions`, automatically sync the live options snapshot
into the format consumed by `exit_monitor`, so `just positions` reflects reality
without manual CSV edits.

---

## Outcome spec

When done, the following must be true:

1. `just ibkr-positions` (or a new `just ibkr-sync`) writes a file
   `reports/output/options_tracker_live.csv` derived from live IBKR option positions.
2. `just positions-live` invokes `exit_monitor` using `options_tracker_live.csv`
   instead of the manual `options_tracker.csv`.
3. The live CSV contains at minimum: `symbol`, `underlying`, `option_type`,
   `strike`, `expiration`, `quantity`, `premium_received`, `current_value`,
   `unrealized_pnl`, `dte`.
4. DTE is computed from today's date vs the expiration field.
5. Exit alerts (DTE ≤ 7) and watch alerts (DTE ≤ 14) are printed correctly
   for all 4 July positions.
6. Existing `just positions` (manual CSV path) continues to work unchanged.
7. `uv run pytest tests/ibkr_positions/` passes.

---

## Constraints

- Read-only: no order submission, no IBKR write operations.
- No async. Synchronous only.
- Do not modify `exit_monitor.py` logic — only the data source feeding it.
- `options_tracker.csv` (manual) is not deleted or modified.
- No new external dependencies beyond `ib_insync` (already in use).

---

## Key design

```
ibkr_positions.main
    → fetches positions (already done)
    → NEW: filter positions where asset_type == "OPT"
    → NEW: build DataFrame matching options_tracker.csv schema
    → write reports/output/options_tracker_live.csv

just positions-live
    → runs exit_monitor with --portfolio reports/output/options_tracker_live.csv
```

Schema mapping from `ibkr_positions.models.Position` to `options_tracker.csv`:

| options_tracker column | source field |
|---|---|
| symbol | position.symbol |
| underlying | position.underlying |
| option_type | position.option_type (CALL/PUT) |
| strike | position.strike |
| expiration | position.expiration |
| quantity | position.quantity |
| premium_received | position.cost_basis (premium received for shorts) |
| current_value | position.market_value |
| unrealized_pnl | position.unrealized_pnl |
| dte | (date.fromisoformat(position.expiration) − date.today()).days |

Files to create/modify:
```
src/ibkr_positions/options_export.py   ← NEW: build options_tracker_live.csv
src/ibkr_positions/main.py             ← call options_export after existing report
tests/ibkr_positions/test_options_export.py ← NEW
justfile                               ← add positions-live recipe
```

---

## Justfile additions

```just
# Exit monitor using live IBKR positions (auto-synced)
positions-live scan="reports/market_scanner/scan_daily.csv" \
               dte_exit_days="7" dte_watch_days="14":
    PYTHONPATH=src uv run python -m market_scanner.exit_monitor \
      --scan {{scan}} \
      --recommendations reports/market_scanner/execution_recommended_rules.csv \
      --portfolio reports/output/options_tracker_live.csv \
      --dte-exit-days {{dte_exit_days}} \
      --dte-watch-days {{dte_watch_days}}
```

---

## Tests (minimum 5)

```python
def test_option_positions_are_extracted_from_portfolio()
# Given a Portfolio with STK + OPT positions, only OPT rows are exported

def test_dte_computed_correctly()
# Position expiring 2026-07-17, today 2026-06-23 → DTE = 24

def test_csv_schema_matches_options_tracker_columns()
# All required columns present in output CSV

def test_short_position_premium_maps_to_cost_basis()
# quantity < 0, cost_basis = premium received

def test_no_options_produces_empty_csv_not_error()
# Portfolio with zero OPT positions writes an empty CSV with headers, no crash
```

---

## Verification

```bash
# 1. Run live fetch (IB Gateway must be running)
just ibkr-positions

# 2. Confirm live CSV was written
cat reports/output/options_tracker_live.csv

# 3. Run exit monitor on live data
just positions-live

# Expected: DTE=24 for all July positions → WATCH alert (≤14 when DTE ≤ 14)

# 4. Tests
uv run pytest tests/ibkr_positions/ -v

# 5. Lint
uv run ruff check src/ibkr_positions/options_export.py \
  tests/ibkr_positions/test_options_export.py
```

---

## Known limitations / follow-up

- Delta not available without market data subscription (IBKR API limitation).
  Deferred to T03 (delta enrichment via options chain).
- `options_tracker_live.csv` is a point-in-time snapshot; it does not persist
  historical entries. Manual `options_tracker.csv` remains the historical record.

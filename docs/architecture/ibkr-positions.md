# ibkr_positions

## Purpose

Reads live portfolio state from IB Gateway via the TWS API and generates a
risk + performance report as Markdown, CSV, and HTML.

This module is read-only. It never submits or modifies orders.

---

## Usage

```bash
just ibkr-positions                        # auto-detects Windows host IP; also syncs trades + rebuilds options_tracker.csv
just ibkr-positions port=4001              # live account (default: 7496)
just ibkr-positions output-dir=reports/my  # custom output dir
just ibkr-history 30                       # last 30 daily account snapshots
just positions-live reports/my/options_tracker_live.csv
```

`ibkr-positions` automatically runs `ibkr-sync` (fetch new executions) and
`ibkr-generate-tracker` (rebuild `options_tracker.csv`) before the report.
See `ibkr-trades.md` for the trade history module.

**Prerequisites (WSL2 → Windows):**

- IB Gateway running on Windows, port 7496 (live) or 4002 (paper)
- Configure → Settings → API:
  - "Permitir conexões somente do host local" → unchecked
  - "IPs confiáveis" → add WSL2 IP (`ip addr show eth0 | grep 'inet '`)
  - Restart Gateway after changing trusted IPs
- No port proxy needed — Gateway binds to `0.0.0.0:7496`

WSL2 IP changes on reboot. If connection breaks: get new IP, update Gateway
trusted list, restart Gateway.

---

## Output Files

All files written to `reports/output/` (date-stamped):

| File | Description |
|------|-------------|
| `ibkr_positions_YYYY-MM-DD.md` | Markdown report |
| `ibkr_positions_YYYY-MM-DD.csv` | Flat positions table |
| `ibkr_positions_YYYY-MM-DD.html` | Self-contained HTML with performance report |
| `options_tracker_live.csv` | Live option snapshot consumed by `positions-live` |
| `data/ibkr/history.jsonl` | Upserted daily account snapshot used by `ibkr-history` |

---

`ibkr-positions` updates one history entry per calendar day after a successful
portfolio fetch. Repeated runs on the same day replace that day's entry.
`ibkr-history` reports NLV, cash, unrealized P&L, option P&L, and the premium
represented by currently open short-option positions. This premium is a
point-in-time snapshot, not cumulative realized premium.

---

The IBKR portfolio snapshot does not include each position's opening trade date.
`positions-live` therefore reports `WATCH` with `entry date unavailable` when a
backtest recommendation selects a `bars_N` exit rule. Alignment and DTE rules
continue to evaluate normally.

## Report Sections

### Markdown / HTML

1. **Executive Summary** — NLV, cash, invested capital, margin utilization, excess liquidity
2. **Performance** — unrealized P&L by asset type, per-position return %, visual PnL bars (HTML only)
3. **Open Options** — premium received vs current value vs P&L per leg
4. **Portfolio Allocation** — market value and % of NLV by asset type
5. **Cash by Currency** — balance and settled cash
6. **Risk Analysis** — concentration alerts, margin metrics, cash coverage for short puts
7. **Enhanced Risk** — approximate net option delta, cash shortfall resolution, concentration actions
8. **Actionable Insights** — short premium summary, margin headroom, assignment risk

---

## Module Structure

```
src/ibkr_positions/
├── client.py         — IB Gateway connection via ib_insync; fetches portfolio
├── models.py         — Portfolio, Position, AccountSummary, CashBalance dataclasses
├── risk.py           — concentration_risk, margin_utilization, cash_coverage, etc.
├── report.py         — Markdown + CSV renderer; orchestrates all output
├── html_report.py    — Self-contained HTML renderer with performance section
├── snapshot_store.py — Daily JSONL snapshot upsert and history summary CLI
├── options_export.py — Export live option positions to options_tracker_live.csv
├── reconciler.py     — Diff live IBKR snapshot vs options_tracker.csv; read-only
└── main.py           — CLI entry point (--host, --port, --output-dir, --client-id)
```

---

## Data Model

### `Position`

| Field | Type | Notes |
|-------|------|-------|
| `symbol` | str | IBKR local symbol (options use full contract name) |
| `asset_type` | str | `STK`, `OPT`, `ETF`, `CASH` |
| `quantity` | float | Negative = short |
| `market_value` | float | Current mark-to-market |
| `cost_basis` | float | `avg_cost × abs(qty)` — for short options: premium received |
| `unrealized_pnl` | float | From IBKR; correct for both long and short positions |
| `currency` | str | |
| `expiration` | str \| None | `YYYY-MM-DD` |
| `strike` | float \| None | Options only |
| `option_type` | str \| None | `CALL` \| `PUT` |
| `underlying` | str \| None | Options only |

### `AccountSummary`

NLV, total cash, buying power, initial/maintenance margin, excess liquidity.
`leverage = initial_margin / NLV`.

---

## Risk Calculations

| Function | Logic |
|----------|-------|
| `margin_utilization` | `initial_margin / NLV` |
| `concentration_risk` | symbols where `abs(market_value) / total > 25%` |
| `cash_coverage` | cash vs `sum(abs(qty) × strike × 100)` for all short puts |
| `cash_shortfall_resolution` | ranked close suggestions for short puts that reduce assignment cash shortfall |
| `delta_proxy` | approximate Black-Scholes delta using fixed 30% IV and 5% risk-free rate |
| `portfolio_net_delta` | sum of approximate `delta × quantity × 100` across option positions |
| `options_expiring_soon` | options expiring within 7 calendar days |
| `short_puts_near_assignment` | short puts within 5% of strike |
| `covered_calls_itm` | short calls where underlying > strike |

---

## Reconciliation (`reconciler.py`)

Diffs the live IBKR option snapshot against `options_tracker.csv` and prints
a structured report of discrepancies (positions in one source but not the other,
or quantity mismatches).

```bash
just ibkr-reconcile                # runs ibkr-positions first, then reconciler
just ibkr-reconcile output-dir=reports/output  # custom output dir
```

Output written to `reports/output/reconciliation_YYYY-MM-DD.md`.

The reconciler is **read-only** — it never modifies either file.

Discrepancy categories:

| Category | Meaning |
|----------|---------|
| `only_in_ibkr` | Position live in IBKR but absent from options_tracker.csv |
| `only_in_tracker` | Position in tracker CSV but not found live in IBKR |
| `qty_mismatch` | Quantity differs between sources |

---

## Connection

Uses `ib_insync`. Connects with `readonly=True`, `timeout=10s`, `client_id=10`.
Disconnects immediately after fetching all data.

Live delta is not populated — IBKR does not return Greeks in the portfolio
endpoint without a market data subscription. Reports include an approximate
delta proxy when expiration, strike, option type, and an underlying price proxy
are available.

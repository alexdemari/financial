# ibkr_positions

## Purpose

Reads live portfolio state from IB Gateway via the TWS API and generates a
risk + performance report as Markdown, CSV, and HTML.

This module is read-only. It never submits or modifies orders.

---

## Usage

```bash
just ibkr-positions                        # auto-detects Windows host IP
just ibkr-positions port=4001              # live account (default: 7496)
just ibkr-positions output-dir=reports/my  # custom output dir
```

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

---

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
├── client.py       — IB Gateway connection via ib_insync; fetches portfolio
├── models.py       — Portfolio, Position, AccountSummary, CashBalance dataclasses
├── risk.py         — concentration_risk, margin_utilization, cash_coverage, etc.
├── report.py       — Markdown + CSV renderer; orchestrates all output
├── html_report.py  — Self-contained HTML renderer with performance section
└── main.py         — CLI entry point (--host, --port, --output-dir, --client-id)
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

## Connection

Uses `ib_insync`. Connects with `readonly=True`, `timeout=10s`, `client_id=10`.
Disconnects immediately after fetching all data.

Live delta is not populated — IBKR does not return Greeks in the portfolio
endpoint without a market data subscription. Reports include an approximate
delta proxy when expiration, strike, option type, and an underlying price proxy
are available.

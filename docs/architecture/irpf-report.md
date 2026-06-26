# irpf_report

## Purpose

Generate an IRPF (Brazilian income tax) annual report for foreign-source income
from IBKR closed trades. Converts USD realized P&L to BRL using official PTAX
rates from the BCB API.

Covers closed options and equity trades only. Does not handle BR assets or
dividend income.

---

## Usage

```bash
just irpf year=2025
# or directly:
PYTHONPATH=src uv run python -m irpf_report.main \
  --trades data/ibkr/trades_2025.csv \
  --year 2025 \
  --output reports/irpf/irpf_2025.md
```

**Input:** IBKR Activity Statement → Trades CSV export (UTF-8, comma-delimited).
Download from IBKR Flex Query or the standard Activity Statement.

**Output:** `reports/irpf/irpf_YYYY.md` — Markdown report with per-trade detail,
monthly summary, asset-type breakdown, and annual totals in both USD and BRL.

---

## Module Structure

```
src/irpf_report/
├── trades.py      — Parse IBKR CSV; produce list[Trade]
├── ptax.py        — Fetch PTAX venda rate from BCB; disk-cache per date
├── calculator.py  — Enrich trades with PTAX; aggregate by month and asset type
├── report.py      — Render Markdown report
└── main.py        — CLI entry point (--trades, --year, --output)
```

---

## Data Flow

```
data/ibkr/trades_YYYY.csv
  → trades.parse_ibkr_csv()        # list[Trade]
  → calculator.enrich_trades()     # attach ptax_rate, brl_proceeds
  → calculator.aggregate_by_month()
  → calculator.aggregate_by_asset_type()
  → calculator.compute_totals()
  → report.render_markdown()
  → reports/irpf/irpf_YYYY.md
```

---

## Key Types

### `Trade`

| Field | Type | Notes |
|-------|------|-------|
| `date` | `date` | Trade settlement date |
| `symbol` | `str` | IBKR local symbol |
| `asset_type` | `str` | `STK`, `OPT`, `ETF` |
| `quantity` | `float` | Negative = sell |
| `proceeds` | `float` | USD gross proceeds (positive) |
| `basis` | `float` | USD cost basis |
| `realized_pnl` | `float` | `proceeds - basis` |

### `EnrichedTrade`

`Trade` + `ptax_rate: float | None` + `brl_proceeds: float | None`.
`ptax_rate` is `None` when BCB returned no data for that date after 3-day
lookback.

---

## PTAX Lookup

- Fetches `cotacaoVenda` (selling rate) from BCB Olinda API.
- Falls back up to 3 prior business days for weekends and holidays.
- Caches each date's rate to `data/ibkr/ptax_cache/YYYY-MM-DD.json`.
- Print warning for any trade where PTAX is missing — BRL totals will be
  incomplete for those rows.

---

## Report Sections

1. **Per-trade detail** — date, symbol, asset type, USD P&L, PTAX rate, BRL P&L
2. **Monthly summary** — total USD P&L and BRL P&L per month
3. **Asset-type breakdown** — totals grouped by `STK`, `OPT`, `ETF`
4. **Annual totals** — grand total USD and BRL realized P&L

---

## Limitations

- Reads only closed-trade rows from the IBKR export. Open positions are ignored.
- Does not net wash-sale adjustments (not required for BR tax residents on
  foreign-source income under current RFB rules).
- BRL conversion uses PTAX venda (selling rate) per RFB Instrução Normativa guidance.

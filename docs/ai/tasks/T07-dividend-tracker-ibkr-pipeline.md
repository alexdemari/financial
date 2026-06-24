# Task: Pipeline IBKR → `dividend_tracker` — USD Dividend Projection + Cash Coverage

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/dividend_tracker/`, `justfile`
**Effort:** S
**Depends on:** T01 (live options export), T06 (snapshot store — optional, for cash figure)

---

## Context

`dividend_tracker` manages a dividend portfolio that includes US assets:
SCHD, DGRO, VYM, and PEP (monitored via put selling). Currently the module
operates independently of the IBKR account — it does not know how many shares
are held, what cash is available in USD, or what dividend income is expected.

The IBKR account holds SGOV (×200 shares, $20,120 market value) and AAPL
(×100 shares). Future USD dividend positions (e.g., SCHD) would also be held there.

Two gaps:
1. `dividend_tracker` cannot project USD dividend income (doesn't know share counts).
2. There is no view of when USD cash will arrive from dividends vs option premium,
   making cash coverage planning for future CSPs opaque.

---

## Goal

Add an optional IBKR positions file input to `dividend_tracker` so it can:
1. Cross-reference positions held in IBKR against the US assets in
   `config/dividend_portfolio.yaml`.
2. Project expected annual dividend income in USD per held asset.
3. Incorporate USD cash available (from IBKR snapshot) into the budget section
   of the dividend daily report.

---

## Outcome spec

When done, the following must be true:

1. `just dividends-ibkr` runs the full dividend analysis using the latest IBKR
   positions snapshot to enrich US asset data.
2. For each US asset in the portfolio config that is also held in IBKR:
   - Show current shares held.
   - Show projected annual dividend income (shares × trailing annual dividend per share).
   - Show current DY on cost basis.
3. The dividend report gains a new section "USD Income Projection" with:
   - Per-asset: symbol, shares, annual_div_per_share, projected_annual_income_usd.
   - Total projected USD income / year.
   - USD cash available (from IBKR snapshot).
4. PEP (monitored asset, `target_weight=0.0`) shows projected income IF shares
   are held (e.g., after assignment of the CSP).
5. If no IBKR snapshot is provided, the section is omitted and behavior is
   unchanged (backward compatible).
6. `uv run pytest tests/dividend_tracker/` passes; no existing tests broken.
7. 3 new tests added.

---

## Constraints

- `dividend_tracker` must NOT import from `ibkr_positions` at module level.
  Data is passed via file path (CSV) or a simple dict — no circular imports.
- No new network calls: share counts come from the IBKR CSV written by
  `just ibkr-positions`. Dividend per share data comes from the existing
  yfinance cache already used by `dividend_tracker`.
- No changes to `config/dividend_portfolio.yaml` schema.
- The IBKR positions CSV schema is the one written by T01
  (`options_tracker_live.csv`) for options, but the main positions CSV
  (`ibkr_positions_YYYY-MM-DD.csv`) contains all position types including STK.
  Use the main positions CSV.

---

## Key design

### New file: `src/dividend_tracker/ibkr_enricher.py`

```python
from pathlib import Path
import pandas as pd
from dataclasses import dataclass

@dataclass
class IBKRHolding:
    symbol: str
    quantity: float
    market_value: float
    cost_basis: float

def load_ibkr_stk_positions(positions_csv: Path) -> dict[str, IBKRHolding]:
    """
    Reads the ibkr_positions CSV and returns a dict of STK/ETF positions
    keyed by symbol (uppercased, no suffix).
    """
    df = pd.read_csv(positions_csv)
    stk = df[df["asset_type"].isin(["STK", "ETF"])].copy()
    return {
        row["symbol"].upper(): IBKRHolding(
            symbol=row["symbol"],
            quantity=row["quantity"],
            market_value=row["market_value"],
            cost_basis=row["cost_basis"],
        )
        for _, row in stk.iterrows()
    }

def project_annual_income(
    holdings: dict[str, IBKRHolding],
    dividend_data: dict[str, float],  # symbol → trailing annual div per share
) -> list[dict]:
    """
    Returns a list of income projection dicts for held dividend assets.
    """
    results = []
    for symbol, holding in holdings.items():
        annual_div = dividend_data.get(symbol)
        if annual_div is None:
            continue
        projected = holding.quantity * annual_div
        dy_on_cost = (annual_div / (holding.cost_basis / holding.quantity) * 100
                      if holding.quantity > 0 else 0)
        results.append({
            "symbol": symbol,
            "shares": holding.quantity,
            "annual_div_per_share": annual_div,
            "projected_annual_income_usd": projected,
            "dy_on_cost_pct": dy_on_cost,
        })
    return results
```

### Modified: `src/dividend_tracker/main.py`

Add `--ibkr-positions PATH` optional flag. When provided:
1. Call `load_ibkr_stk_positions()` to get held shares.
2. Reuse existing dividend data (already fetched by the main flow) to get
   trailing annual dividend per share.
3. Call `project_annual_income()`.
4. Pass results to report renderer for the new section.

### Justfile

```just
# Dividend analysis enriched with live IBKR positions
dividends-ibkr budget="":
    #!/usr/bin/env bash
    set -euo pipefail
    SNAPSHOT=$(ls reports/output/ibkr_positions_*.csv 2>/dev/null | sort | tail -1)
    if [ -z "$SNAPSHOT" ]; then
        echo "No IBKR snapshot found. Run 'just ibkr-positions' first."
        exit 1
    fi
    tickers=$(PYTHONPATH=src uv run python -c "...")
    PYTHONPATH=src uv run python -m stock_data_manager.main -s ${tickers}
    PYTHONPATH=src uv run python -m dividend_tracker.main \
        --ibkr-positions "$SNAPSHOT" \
        {{ if budget != "" { "--budget " + budget } else { "" } }} \
        --output reports/dividend_tracker/dividend_daily_report.md
    echo "Relatorio gerado: reports/dividend_tracker/dividend_daily_report.md"
```

Files to create/modify:
```
src/dividend_tracker/ibkr_enricher.py          ← NEW
src/dividend_tracker/main.py                   ← add --ibkr-positions flag
src/dividend_tracker/report.py                 ← add USD Income Projection section
tests/dividend_tracker/test_ibkr_enricher.py   ← NEW
justfile                                       ← add dividends-ibkr recipe
```

---

## Report section added

```markdown
## USD Income Projection (based on IBKR positions)

| Symbol | Shares | Div/Share/Year | Projected Annual Income | DY on Cost |
|--------|--------|---------------|------------------------|-----------|
| SGOV   | 200    | $5.18         | $1,036/year            | 5.14%     |

**Total projected USD income:** $1,036/year (~$86/month)
**USD cash available (IBKR):** $14,023

*Note: projections use trailing 12-month dividends per share. Not a guarantee of future income.*
```

---

## Tests (minimum 3)

```python
def test_load_ibkr_stk_positions_filters_out_options(tmp_path)
# CSV with STK + OPT rows → only STK returned

def test_project_annual_income_multiplies_shares_by_div(tmp_path)
# 200 shares × $5.18/share → projected = $1,036

def test_ibkr_enricher_graceful_when_symbol_not_in_dividend_data()
# Holding in IBKR not in dividend data → skipped, no crash
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/dividend_tracker/test_ibkr_enricher.py -v

# 2. Live run
just ibkr-positions   # ensure snapshot exists
just dividends-ibkr budget=8000

# Check report for USD Income Projection section
grep -A 20 "USD Income Projection" reports/dividend_tracker/dividend_daily_report.md

# 3. Backward compat — original dividends recipe unchanged
just dividends budget=8000

# 4. Lint
uv run ruff check src/dividend_tracker/ibkr_enricher.py
```

---

## Known limitations / follow-up

- SGOV is a T-bill ETF, not a traditional dividend asset. Its "dividends" are
  interest income distributions. The projection is numerically correct but the
  label "dividend" may be misleading. A future task could add an `income_type`
  field (dividend / interest / return_of_capital).
- Does not project option premium income. Premium income from covered calls
  and CSPs is tracked separately in `options_tracker.csv`.

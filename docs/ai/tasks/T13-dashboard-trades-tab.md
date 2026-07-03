# Task T13: Dashboard — Aba "Trades Realizados" (IBKR + BTG unificados)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/web/readers/trades_reader.py` (new), `src/web/routers/trades.py` (new), `frontend/src/components/TradesTable.jsx` (new)
**Effort:** S
**Depends on:** T12 (dashboard Phase 1 running), T09 (trades_history.csv exists)
**Precedes:** T14 (BTG parser — needed to show BTG trades in this tab)

---

## Context

`data/ibkr/trades_history.csv` contains the full IBKR trade history from account
inception, populated by T09/T10. The dashboard (T12) has no tab for realized
trades — only open positions are shown.

After T14, `data/btg/trades_history.csv` will contain BTG trade history in the
same canonical schema. This task builds the unified trades tab that reads both
sources and merges them into a single view.

The tab is built now (T13) using IBKR data only, with a BTG slot already
wired in so T14 just drops in a new reader with no frontend changes.

---

## Goal

Add a "Trades" tab to the dashboard that shows all realized operations across
IBKR (and BTG once T14 is done), filterable by period, broker, and asset type,
with a monthly P&L summary panel.

---

## Outcome spec

When done, the following must be true:

1. A "Trades" tab appears in the dashboard navigation alongside Portfolio,
   History, Scanner, Dividends.
2. The tab shows a table of **closed trades only** (rows where `open_close`
   contains `"C"` and `pnl_realized` is not null), sorted by date descending.
3. Table columns: Date, Broker, Symbol, Type (STK/OPT/ETF), Direction
   (BUY/SELL), Qty, Price, Proceeds, P&L (USD or BRL depending on broker),
   Strategy (covered_call / csp / roll / other).
4. Filters (all client-side, no new API calls):
   - Period: Last 30d / 90d / 6m / 1y / All
   - Broker: All / IBKR / BTG-Opções / BTG-Geral
   - Type: All / STK / OPT / ETF
5. Monthly summary panel above the table:
   - Per month: Gross gains, Gross losses, Net P&L, Trade count
   - Currency shown per row (USD for IBKR, BRL for BTG)
6. Options trades show additional columns: Strike, Expiration, Strategy
   (collapsible on mobile — always visible on desktop).
7. `GET /api/trades` returns merged data from all available sources.
   If `data/btg/` files do not exist yet, IBKR-only data is returned
   without error.
8. A "last updated" line shows the mtime of each source file.
9. `uv run pytest tests/web/test_trades_reader.py` passes (≥ 5 tests).

---

## Constraints

- **Client-side filtering only.** `/api/trades` returns all closed trades;
  the frontend filters. Avoids multiple API roundtrips for filter changes.
- Currency is NOT converted. IBKR trades stay in USD, BTG trades in BRL.
  A currency column makes this explicit. Consolidated totals are deferred to T15.
- No changes to `trades_history.csv` schema or `ibkr_trades` module.
- The BTG slot is wired but returns `[]` if `data/btg/` does not exist.
  T14 fills it in — T13 has zero dependency on T14 being done.
- Read-only. No write operations.

---

## Canonical trade schema for the API response

Both IBKR and BTG trades are normalized to this shape before the API returns:

```python
@dataclass
class TradeRow:
    date: str           # YYYY-MM-DD
    broker: str         # "IBKR" | "BTG-Opções" | "BTG-Geral"
    symbol: str         # e.g. "AAPL  260717C00310000" or "TAEE11"
    underlying: str     # e.g. "AAPL" or "TAEE11"
    asset_type: str     # STK | OPT | ETF | BDR | FI
    direction: str      # BUY | SELL
    quantity: float
    price: float
    proceeds: float
    commission: float
    pnl_realized: float
    currency: str       # USD | BRL
    strategy: str | None  # covered_call | csp | roll | other | None
    # Options only
    option_type: str | None   # CALL | PUT
    strike: float | None
    expiration: str | None    # YYYY-MM-DD
```

---

## Key design

### Reader: `src/web/readers/trades_reader.py`

```python
from pathlib import Path
import pandas as pd
from web.readers.models import TradeRow

IBKR_HISTORY   = Path("data/ibkr/trades_history.csv")
BTG_OPCOES     = Path("data/btg/btg_opcoes_trades.csv")
BTG_GERAL      = Path("data/btg/btg_geral_trades.csv")

def read_all_trades() -> list[dict]:
    """
    Reads and merges closed trades from all available sources.
    Returns list of TradeRow dicts, sorted by date descending.
    """
    rows = []
    rows += _read_ibkr_trades()
    rows += _read_btg_trades(BTG_OPCOES, broker="BTG-Opções")
    rows += _read_btg_trades(BTG_GERAL,  broker="BTG-Geral")
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows

def _read_ibkr_trades() -> list[dict]:
    if not IBKR_HISTORY.exists():
        return []
    df = pd.read_csv(IBKR_HISTORY, dtype={"trade_id": str})
    # Keep only closed trades with realized P&L
    closed = df[
        df["open_close"].str.contains("C", na=False) &
        df["pnl_realized"].notna()
    ]
    return [_ibkr_row_to_trade(row) for _, row in closed.iterrows()]

def _read_btg_trades(path: Path, broker: str) -> list[dict]:
    """Reads BTG canonical trades CSV (written by T14 parser)."""
    if not path.exists():
        return []
    df = pd.read_csv(path)
    return [_btg_row_to_trade(row, broker) for _, row in df.iterrows()]

def read_monthly_summary(trades: list[dict]) -> list[dict]:
    """
    Aggregates trades by (year_month, currency) into monthly P&L summary.
    Returns list sorted by month descending.
    """
    ...
```

### Router: `src/web/routers/trades.py`

```python
from fastapi import APIRouter
from web.readers.trades_reader import read_all_trades, read_monthly_summary

router = APIRouter(prefix="/api")

@router.get("/trades")
def get_trades():
    trades = read_all_trades()
    monthly = read_monthly_summary(trades)
    return {
        "trades": trades,
        "monthly_summary": monthly,
        "sources": {
            "ibkr": str(IBKR_HISTORY) if IBKR_HISTORY.exists() else None,
            "btg_opcoes": str(BTG_OPCOES) if BTG_OPCOES.exists() else None,
            "btg_geral":  str(BTG_GERAL)  if BTG_GERAL.exists()  else None,
        }
    }
```

Register in `src/web/server.py`:
```python
from web.routers import trades
app.include_router(trades.router)
```

### Frontend: `frontend/src/components/TradesTable.jsx`

```jsx
// Tabs: Summary | All Trades
// Summary: monthly P&L cards (per currency)
// All Trades: filterable table

const PERIOD_OPTIONS = [
  { label: "30d",  days: 30  },
  { label: "90d",  days: 90  },
  { label: "6m",   days: 180 },
  { label: "1y",   days: 365 },
  { label: "Tudo", days: null },
];

function filterTrades(trades, { period, broker, type }) {
  let result = trades;
  if (period) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - period);
    result = result.filter(t => new Date(t.date) >= cutoff);
  }
  if (broker !== "all") result = result.filter(t => t.broker === broker);
  if (type  !== "all") result = result.filter(t => t.asset_type === type);
  return result;
}
```

Monthly summary card example:
```
Jun 2026  │  USD  Ganhos: $312  Perdas: -$113  Líquido: +$199  (4 trades)
Jun 2026  │  BRL  Ganhos: R$0   Perdas: R$0    Líquido: R$0    (0 trades)
```

---

## Files to create/modify

```
src/web/readers/trades_reader.py          ← NEW
src/web/routers/trades.py                 ← NEW
src/web/server.py                         ← register trades router
frontend/src/App.jsx                      ← add "Trades" tab
frontend/src/components/TradesTable.jsx   ← NEW
tests/web/test_trades_reader.py           ← NEW
```

---

## Tests (minimum 5)

```python
def test_read_ibkr_trades_returns_only_closed(tmp_path, monkeypatch)
# CSV with O + C rows → only C rows with pnl_realized returned

def test_read_btg_trades_returns_empty_when_file_missing(monkeypatch)
# BTG file does not exist → [] returned, no crash

def test_trade_row_has_all_required_fields(tmp_path, monkeypatch)
# Single IBKR closed trade → TradeRow has date, broker, symbol, pnl_realized, currency

def test_monthly_summary_groups_by_month_and_currency(tmp_path, monkeypatch)
# 3 USD trades in Jun, 2 BRL trades in Jun → 2 summary rows for Jun

def test_merged_trades_sorted_by_date_descending(tmp_path, monkeypatch)
# IBKR trade 2026-06-01 + BTG trade 2026-05-15 → IBKR trade first
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/web/test_trades_reader.py -v

# 2. Start dashboard and open Trades tab
just web
# Navigate to http://localhost:8000 → "Trades" tab

# 3. Verify IBKR trades visible
# Expected: closed options trades from July (AAPL CC, SMR, PEP, FSLY) if any are closed

# 4. Verify filter works
# Select "OPT" type → only options trades visible
# Select "BTG-Opções" → empty table with "No data yet" message

# 5. Lint
uv run ruff check src/web/readers/trades_reader.py \
  src/web/routers/trades.py tests/web/test_trades_reader.py
```

---

## Known limitations / follow-up

- Currency conversion (USD → BRL) for consolidated total is deferred to T15,
  which will use the PTAX rate from the BCB cache built by `irpf_report`.
- BTG options trades from the extrato show open positions (BBASH212) but
  the movimentação section shows COMPRA/VENDA de opções BR (EGIER324,
  PETRR417) — these will be parsed by T14 and appear here automatically.
- P&L for BTG stock trades requires cost basis matching (FIFO or average
  cost per Brazilian rules). T14 handles this — T13 shows `pnl_realized`
  as provided by the BTG parser, which may be null for open-to-close pairs
  not yet matched.

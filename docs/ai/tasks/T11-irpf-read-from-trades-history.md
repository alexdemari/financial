# Task T11: `irpf_report` — Read from `trades_history.csv` (Eliminate Manual Annual Export)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/irpf_report/trades.py`, `src/irpf_report/main.py`, `justfile`
**Effort:** S
**Depends on:** T09 (trades_history.csv canonical store), T10 (flex_fetcher ensures pnl_realized populated)

---

## Context

`irpf_report` currently expects a separate IBKR Activity Statement CSV export
downloaded manually from the portal for each calendar year:

```bash
just irpf year=2025
# reads: data/ibkr/trades_2025.csv  ← manual annual export required
```

Since T09 was completed, `data/ibkr/trades_history.csv` now contains the
complete trade history from account inception, including `pnl_realized` per
closed trade (populated via Flex XML from T10). This is exactly the data
`irpf_report` needs — no additional export required.

The two inputs differ only in format:
- `trades_2025.csv`: raw IBKR Activity Statement format (multi-section CSV,
  requires header detection and section parsing)
- `trades_history.csv`: canonical `TradeRecord` schema from `ibkr_trades`
  (clean, single-header CSV, already normalized)

This task adds `--history` as an alternative input mode to `irpf_report.main`,
making the annual manual CSV export optional (kept for backward compatibility
and as a fallback when `trades_history.csv` is not available).

---

## Goal

Extend `irpf_report` to accept `--history data/ibkr/trades_history.csv --year 2025`
as an alternative to `--trades data/ibkr/trades_2025.csv`. When `--history` is
provided, filter by `date LIKE '2025-%'` and closed trades (`pnl_realized IS NOT NULL`),
then proceed through the existing enrichment and report pipeline unchanged.

---

## Outcome spec

When done, the following must be true:

1. `just irpf year=2025` works in two modes:
   - **History mode** (default when `trades_history.csv` exists):
     `--history data/ibkr/trades_history.csv --year 2025`
   - **Legacy mode** (fallback when history file absent, or `--trades` explicitly passed):
     `--trades data/ibkr/trades_2025.csv --year 2025`
2. Both modes produce an identical `reports/irpf/irpf_YYYY.md` for the same
   underlying data.
3. A new function `parse_history_csv(path, year)` in `irpf_report/trades.py`
   reads `trades_history.csv`, filters to the given year and to rows where
   `pnl_realized` is not null, and returns `list[Trade]`.
4. `parse_history_csv` maps `TradeRecord` columns to the existing `Trade`
   dataclass used by `calculator.py` — no changes to `calculator.py` or
   `report.py`.
5. If `--history` is used but `pnl_realized` is null for some rows (i.e., T10
   not yet fully run), those rows are skipped with a printed warning per row:
   `"⚠ Skipping {symbol} {date}: pnl_realized missing (run just ibkr-flex-fetch)"`.
6. `uv run pytest tests/irpf_report/` passes; no existing tests broken.
7. 4 new tests added in `tests/irpf_report/test_history_reader.py`.

---

## Constraints

- `calculator.py`, `ptax.py`, and `report.py` are **not modified**.
  All changes are confined to `trades.py` and `main.py`.
- The existing `--trades` flag and `parse_ibkr_csv()` function are preserved
  unchanged — backward compatibility is mandatory.
- `parse_history_csv` must not import from `ibkr_trades` — it reads the CSV
  directly with `pandas`. No circular imports.
- Only closed trades contribute to IRPF: rows where `open_close` contains `"C"`
  **and** `pnl_realized` is not null. Opening trades are excluded.
- `asset_type` filter: include `STK`, `OPT`, `ETF`. Exclude `CASH` rows.
- `year` filter: applied on the `date` column (trade date, not settlement date).

---

## Key design

### Column mapping: `TradeRecord` → `Trade`

| `trades_history.csv` column | `Trade` field | Notes |
|---|---|---|
| `date` | `date` | Already `YYYY-MM-DD` |
| `symbol` | `symbol` | |
| `asset_type` | `asset_type` | |
| `quantity` | `quantity` | |
| `proceeds` | `proceeds` | USD gross proceeds |
| `pnl_realized` | `realized_pnl` | Core field for IRPF |
| `proceeds - pnl_realized` | `basis` | Derived: cost basis = proceeds − P&L |
| `currency` | *(validation only)* | Assert == "USD", warn if not |

### New function in `src/irpf_report/trades.py`

```python
def parse_history_csv(path: Path, year: int) -> list[Trade]:
    """
    Reads trades_history.csv (ibkr_trades canonical schema) and returns
    closed trades for the given calendar year as list[Trade].

    Filters:
    - date starts with str(year)
    - open_close contains 'C'
    - pnl_realized is not null
    - asset_type in ('STK', 'OPT', 'ETF')

    Rows with null pnl_realized are skipped with a warning.
    """
    import pandas as pd

    df = pd.read_csv(path, dtype={"trade_id": str, "pnl_realized": float})

    # Year filter
    df = df[df["date"].str.startswith(str(year))]

    # Asset type filter
    df = df[df["asset_type"].isin(["STK", "OPT", "ETF"])]

    # Closed trades only
    df = df[df["open_close"].str.contains("C", na=False)]

    trades = []
    for _, row in df.iterrows():
        if pd.isna(row.get("pnl_realized")):
            print(
                f"⚠ Skipping {row['symbol']} {row['date']}: "
                f"pnl_realized missing (run: just ibkr-flex-fetch)"
            )
            continue

        trades.append(Trade(
            date         = date.fromisoformat(row["date"]),
            symbol       = row["symbol"],
            asset_type   = row["asset_type"],
            quantity     = float(row["quantity"]),
            proceeds     = float(row["proceeds"]),
            basis        = float(row["proceeds"]) - float(row["pnl_realized"]),
            realized_pnl = float(row["pnl_realized"]),
        ))

    return trades
```

### Updated `src/irpf_report/main.py`

```python
parser.add_argument("--trades",  type=Path, default=None,
    help="IBKR Activity Statement CSV (legacy input)")
parser.add_argument("--history", type=Path, default=None,
    help="trades_history.csv from ibkr_trades (preferred input)")
parser.add_argument("--year", type=int, required=True)

# Resolution logic
if args.history:
    trades = parse_history_csv(args.history, args.year)
elif args.trades:
    trades = parse_ibkr_csv(args.trades)
else:
    # Auto-detect: prefer history if it exists
    default_history = Path("data/ibkr/trades_history.csv")
    default_trades  = Path(f"data/ibkr/trades_{args.year}.csv")
    if default_history.exists():
        print(f"Using trades_history.csv (run 'just ibkr-flex-fetch' to refresh)")
        trades = parse_history_csv(default_history, args.year)
    elif default_trades.exists():
        print(f"Using legacy trades CSV: {default_trades}")
        trades = parse_ibkr_csv(default_trades)
    else:
        parser.error(
            f"No trade data found. Provide --history or --trades, "
            f"or run 'just ibkr-trades-daily' first."
        )
```

### Updated `justfile`

```just
# Generate BRL IRPF report for a given year.
# Uses trades_history.csv if available (preferred); falls back to manual CSV.
irpf year="2025":
    #!/usr/bin/env bash
    set -euo pipefail
    HISTORY="data/ibkr/trades_history.csv"
    LEGACY="data/ibkr/trades_{{year}}.csv"
    if [ -f "$HISTORY" ]; then
        echo "Using trades_history.csv for IRPF {{year}}"
        PYTHONPATH=src uv run python -m irpf_report.main \
            --history "$HISTORY" \
            --year {{year}} \
            --output reports/irpf/irpf_{{year}}.md
    elif [ -f "$LEGACY" ]; then
        echo "Using legacy CSV: $LEGACY"
        PYTHONPATH=src uv run python -m irpf_report.main \
            --trades "$LEGACY" \
            --year {{year}} \
            --output reports/irpf/irpf_{{year}}.md
    else
        echo "Error: no trade data found."
        echo "Run 'just ibkr-trades-daily' or provide data/ibkr/trades_{{year}}.csv"
        exit 1
    fi
    echo "✓ IRPF report: reports/irpf/irpf_{{year}}.md"
```

Files to create/modify:
```
src/irpf_report/trades.py                   ← add parse_history_csv()
src/irpf_report/main.py                     ← add --history flag + auto-detect logic
tests/irpf_report/test_history_reader.py    ← NEW (4 tests)
justfile                                    ← update irpf recipe
```

---

## Tests (4 new, in `tests/irpf_report/test_history_reader.py`)

```python
def test_parse_history_csv_filters_by_year(tmp_path)
# History with trades in 2024 and 2025 → year=2025 returns only 2025 rows

def test_parse_history_csv_excludes_open_trades(tmp_path)
# Row with open_close='O' and pnl_realized set → excluded from result

def test_parse_history_csv_skips_null_pnl_with_warning(tmp_path, capsys)
# Row with open_close='C' but pnl_realized=null → skipped; warning printed to stdout

def test_parse_history_csv_basis_derived_correctly(tmp_path)
# proceeds=500, pnl_realized=150 → basis=350; Trade.realized_pnl=150
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/irpf_report/test_history_reader.py -v

# 2. Ensure T10 has run so pnl_realized is populated
just ibkr-flex-fetch
just ibkr-backfill flex=data/ibkr/flex_latest.xml

# 3. Generate IRPF using history (auto-detected)
just irpf year=2025
# Expected: "Using trades_history.csv for IRPF 2025"
cat reports/irpf/irpf_2025.md

# 4. Verify same output with legacy CSV (regression check)
just irpf year=2025   # but rename trades_history.csv temporarily to force fallback
# Expected: "Using legacy CSV: data/ibkr/trades_2025.csv"

# 5. Lint
uv run ruff check src/irpf_report/trades.py \
  src/irpf_report/main.py \
  tests/irpf_report/test_history_reader.py
```

---

## Known limitations / follow-up

- `basis` is derived as `proceeds − pnl_realized`. This is correct for FIFO
  P&L (which IBKR uses by default) but may differ from average-cost basis.
  The BCB/RFB guideline for foreign-source income accepts FIFO; no change needed.
- Wash-sale adjustments are not handled (not required for Brazilian IRPF on
  foreign income under current RFB rules).
- Currency validation warns on non-USD rows but does not crash. Multi-currency
  support (e.g., EUR-denominated positions) is out of scope.
- Once `trades_history.csv` is the standard input, `data/ibkr/trades_YYYY.csv`
  files can be removed from the project. This cleanup is not automated here —
  do it manually after confirming the history-based output is correct.

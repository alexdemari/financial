# Task: IBKR Trade History Store — Auto-generate `options_tracker.csv` from Execution Records

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/ibkr_trades/` (new module), `justfile`
**Effort:** L
**Depends on:** T01 (ibkr_positions models and connection pattern established)

---

## Context

`options_tracker.csv` is currently maintained manually: every time a position
is opened, closed, or rolled on IBKR, the file must be edited by hand. This
creates three problems:

1. **Lag** — the file is always slightly stale relative to the real account.
2. **Errors** — manual entry of strikes, premiums, and dates is error-prone.
3. **Incomplete history** — positions opened before the tracking habit was
   established are missing entirely.

IBKR provides two complementary data sources to solve this permanently:

- **Flex Query** (XML/CSV export via web portal) — complete trade history from
  account inception, including all executions, commissions, and P&L. This is a
  one-time manual export used for the initial backfill only.
- **Client Portal API `/iserver/account/trades`** — returns the last N days of
  executions via the already-established `ib_insync` connection. Used for
  incremental daily sync.

### Design principle

`options_tracker.csv` becomes a **derived artifact**, not a source of truth.
The canonical store is `data/ibkr/trades_history.csv` (or SQLite in a future
task). `options_tracker.csv` is regenerated from the store on demand, preserving
full backward compatibility with `exit_monitor` and every other consumer.

```
IBKR (Flex Query XML)          ← one-time backfill
IBKR (Client Portal API)       ← daily incremental sync
        ↓
data/ibkr/trades_history.csv   ← canonical store (append-only, gitignored)
        ↓
options_tracker.csv            ← derived: open option legs only
        ↓
exit_monitor / daily_report    ← unchanged consumers
```

---

## Goal

Create `ibkr_trades` module that:

1. Parses a Flex Query XML/CSV export and populates `trades_history.csv` (backfill).
2. Fetches new executions from the Client Portal API and appends them (incremental sync).
3. Derives and writes `options_tracker.csv` from all open option legs in the history.
4. Detects rolls (same-day close + open of same underlying/expiry/type) and tags them.

---

## Outcome spec

When done, the following must be true:

1. `just ibkr-backfill flex=data/ibkr/flex_export.xml` parses the Flex Query
   XML and writes `data/ibkr/trades_history.csv` with all historical executions.
2. `just ibkr-sync` fetches new trades since the last sync date and appends them
   to `trades_history.csv` without duplicates (idempotent by `trade_id`).
3. `just ibkr-generate-tracker` reads `trades_history.csv` and writes
   `options_tracker.csv` containing only currently open option legs.
4. `options_tracker.csv` has the same schema as today (backward compatible with
   `exit_monitor`). New columns (`trade_id`, `roll_id`, `strategy`) are additive
   and optional — `exit_monitor` ignores unknown columns.
5. Rolled positions are detected and tagged: the closing leg and the new opening
   leg share a `roll_id` (UUID generated at detection time).
6. `just ibkr-positions` automatically triggers `just ibkr-sync` and
   `just ibkr-generate-tracker` so the full flow runs in one command.
7. `data/ibkr/trades_history.csv` is gitignored (contains account data).
8. `uv run pytest tests/ibkr_trades/` passes (≥ 10 tests).
9. Manual edits to `options_tracker.csv` are no longer needed after first sync.

---

## Constraints

- Read-only: no order submission, no IBKR write operations.
- No async. Synchronous only.
- No new pip dependencies beyond `ib_insync` and `pandas` (already in project).
  XML parsing uses `xml.etree.ElementTree` (stdlib).
- `trades_history.csv` is append-only: rows are never deleted or modified
  after being written. Corrections happen via a separate `--fix` flag (out of scope).
- Deduplication key: `trade_id` (IBKR `execId` from API, or `TradeID` from Flex XML).
  Two rows with the same `trade_id` = same execution; the second write is a no-op.
- `options_tracker.csv` is fully regenerated on every `just ibkr-generate-tracker`
  run — it is never edited manually after this task is shipped.
- The existing manual `options_tracker.csv` is archived to
  `data/ibkr/options_tracker_manual_backup_YYYY-MM-DD.csv` the first time
  `ibkr-generate-tracker` runs, not deleted.

---

## Canonical trade record schema

```
trades_history.csv columns:

trade_id        str   IBKR execId or Flex TradeID — deduplication key
date            date  YYYY-MM-DD — trade date (not settlement)
datetime        str   ISO datetime of execution
symbol          str   IBKR local symbol (e.g. "AAPL  260717C00310000")
underlying      str   e.g. "AAPL"
asset_type      str   STK | OPT | ETF | CASH
option_type     str   CALL | PUT | null
strike          float null for non-options
expiration      str   YYYY-MM-DD | null for non-options
quantity        float positive=buy, negative=sell
price           float execution price per unit
proceeds        float quantity × price × multiplier (100 for options)
commission      float negative value
pnl_realized    float null for opening legs; populated on closing legs
currency        str   USD
open_close      str   O | C | O;C (IBKR Code field)
source          str   flex | api
roll_id         str   UUID shared by roll pair | null
strategy        str   covered_call | csp | short_put | long_call | roll | other | null
```

---

## Module structure

```
src/ibkr_trades/
    __init__.py
    models.py           ← TradeRecord dataclass matching schema above
    flex_parser.py      ← Flex Query XML/CSV → list[TradeRecord]
    api_fetcher.py      ← Client Portal API → list[TradeRecord] (incremental)
    store.py            ← trades_history.csv read/write/dedup/append
    roll_detector.py    ← detect rolls, assign roll_id
    strategy_tagger.py  ← infer strategy from open_close + option_type + context
    tracker_builder.py  ← derive options_tracker.csv from open legs in history
    main.py             ← CLI: backfill | sync | generate-tracker
tests/ibkr_trades/
    test_flex_parser.py
    test_api_fetcher.py
    test_store.py
    test_roll_detector.py
    test_tracker_builder.py
```

---

## 1. TradeRecord model

```python
# src/ibkr_trades/models.py

from dataclasses import dataclass, field
from datetime import date

@dataclass
class TradeRecord:
    trade_id: str
    date: date
    datetime: str
    symbol: str
    underlying: str
    asset_type: str           # STK | OPT | ETF | CASH
    option_type: str | None   # CALL | PUT | None
    strike: float | None
    expiration: str | None    # YYYY-MM-DD
    quantity: float
    price: float
    proceeds: float
    commission: float
    pnl_realized: float | None
    currency: str
    open_close: str           # O | C | O;C
    source: str               # flex | api
    roll_id: str | None = None
    strategy: str | None = None
```

---

## 2. Flex Query parser

IBKR Flex Query XML structure (relevant section):

```xml
<FlexQueryResponse>
  <FlexStatements>
    <FlexStatement accountId="UXXXXXXXX" ...>
      <Trades>
        <Trade
          tradeID="12345678"
          tradeDate="2026-06-10"
          dateTime="2026-06-10;09:35:22"
          symbol="PEP   260717P00140000"
          underlyingSymbol="PEP"
          assetCategory="OPT"
          putCall="P"
          strike="140"
          expiry="2026-07-17"
          quantity="-1"
          tradePrice="2.86"
          proceeds="286"
          ibCommission="-0.71"
          fifoPnlRealized="0"
          currency="USD"
          openCloseIndicator="O"
        />
      </Trades>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
```

```python
# src/ibkr_trades/flex_parser.py

import xml.etree.ElementTree as ET
from pathlib import Path
from ibkr_trades.models import TradeRecord

def parse_flex_xml(path: Path) -> list[TradeRecord]:
    """
    Parses IBKR Flex Query XML export.
    Returns list of TradeRecord for all OPT and STK trades.
    Skips non-trade rows (dividends, fees, transfers).
    """
    tree = ET.parse(path)
    root = tree.getroot()
    records = []

    for trade in root.iter("Trade"):
        asset_cat = trade.get("assetCategory", "")
        if asset_cat not in ("OPT", "STK", "ETF"):
            continue

        records.append(TradeRecord(
            trade_id    = trade.get("tradeID", ""),
            date        = _parse_date(trade.get("tradeDate", "")),
            datetime    = trade.get("dateTime", "").replace(";", "T"),
            symbol      = trade.get("symbol", ""),
            underlying  = trade.get("underlyingSymbol", "") or trade.get("symbol", ""),
            asset_type  = asset_cat,
            option_type = _map_put_call(trade.get("putCall")),
            strike      = _float_or_none(trade.get("strike")),
            expiration  = _format_expiry(trade.get("expiry")),
            quantity    = float(trade.get("quantity", 0)),
            price       = float(trade.get("tradePrice", 0)),
            proceeds    = float(trade.get("proceeds", 0)),
            commission  = float(trade.get("ibCommission", 0)),
            pnl_realized= _float_or_none(trade.get("fifoPnlRealized")),
            currency    = trade.get("currency", "USD"),
            open_close  = trade.get("openCloseIndicator", ""),
            source      = "flex",
        ))

    return records
```

---

## 3. Incremental API fetcher

The Client Portal API endpoint `/iserver/account/{accountId}/trades` returns
the most recent executions. `ib_insync` wraps this as `ib.reqExecutions()`.

```python
# src/ibkr_trades/api_fetcher.py

from datetime import date, timedelta
from ib_insync import IB, ExecutionFilter
from ibkr_trades.models import TradeRecord

def fetch_recent_trades(
    ib: IB,
    account_id: str,
    since: date | None = None,
) -> list[TradeRecord]:
    """
    Fetches executions from IB Gateway via ib_insync.
    `since` defaults to 7 days ago if not provided.
    Returns TradeRecord list filtered to OPT and STK.
    """
    since = since or (date.today() - timedelta(days=7))
    fills = ib.reqExecutions(ExecutionFilter(
        acctCode=account_id,
        time=since.strftime("%Y%m%d %H:%M:%S"),
    ))

    records = []
    for fill in fills:
        exec_ = fill.execution
        contract = fill.contract
        if contract.secType not in ("OPT", "STK", "ETF"):
            continue

        records.append(TradeRecord(
            trade_id    = exec_.execId,
            date        = date.fromisoformat(exec_.time[:10]),
            datetime    = exec_.time,
            symbol      = contract.localSymbol,
            underlying  = contract.symbol,
            asset_type  = contract.secType,
            option_type = contract.right if contract.secType == "OPT" else None,
            strike      = contract.strike if contract.secType == "OPT" else None,
            expiration  = _format_expiry(contract.lastTradeDateOrContractMonth),
            quantity    = exec_.shares * (1 if exec_.side == "BOT" else -1),
            price       = exec_.price,
            proceeds    = exec_.shares * exec_.price * (
                100 if contract.secType == "OPT" else 1
            ) * (-1 if exec_.side == "BOT" else 1),
            commission  = 0.0,  # populated separately via CommissionReport
            pnl_realized= None,  # not available from executions endpoint
            currency    = contract.currency,
            open_close  = "",   # not available; inferred by store
            source      = "api",
        ))

    return records
```

---

## 4. Store — append-only with deduplication

```python
# src/ibkr_trades/store.py

from pathlib import Path
import pandas as pd
from ibkr_trades.models import TradeRecord

HISTORY_PATH = Path("data/ibkr/trades_history.csv")

def load_history(path: Path = HISTORY_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"trade_id": str})

def append_trades(
    new_records: list[TradeRecord],
    path: Path = HISTORY_PATH,
) -> tuple[int, int]:
    """
    Appends new_records to the history CSV.
    Deduplicates by trade_id — existing IDs are silently skipped.
    Returns (added_count, skipped_count).
    """
    existing = load_history(path)
    existing_ids: set[str] = set(existing["trade_id"]) if not existing.empty else set()

    new_rows = [r for r in new_records if r.trade_id not in existing_ids]
    skipped  = len(new_records) - len(new_rows)

    if not new_rows:
        return 0, skipped

    new_df = pd.DataFrame([vars(r) for r in new_rows])
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values(["date", "datetime"]).reset_index(drop=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)

    return len(new_rows), skipped

def last_sync_date(path: Path = HISTORY_PATH) -> date | None:
    """Returns the most recent trade date in history, or None if empty."""
    df = load_history(path)
    if df.empty or "date" not in df.columns:
        return None
    return pd.to_datetime(df["date"]).max().date()
```

---

## 5. Roll detector

A roll is detected when, on the same date and for the same underlying, there is:
- A **closing** trade (`open_close == "C"`) on one contract
- An **opening** trade (`open_close == "O"`) on a different expiration or strike
  of the same option type, within a configurable time window (default: same day)

```python
# src/ibkr_trades/roll_detector.py

import uuid
import pandas as pd

def detect_and_tag_rolls(df: pd.DataFrame, window_days: int = 0) -> pd.DataFrame:
    """
    Detects roll pairs in the trade history and assigns a shared roll_id UUID.
    A roll = same-day close (C) + open (O) of same underlying + option_type.
    Modifies df in-place (roll_id column). Returns df.
    """
    df = df.copy()
    df["roll_id"] = df.get("roll_id", None)

    opts = df[df["asset_type"] == "OPT"].copy()
    opts["date"] = pd.to_datetime(opts["date"])

    for date_, group in opts.groupby("date"):
        closes = group[group["open_close"].str.contains("C", na=False)]
        opens  = group[group["open_close"] == "O"]

        for _, close_row in closes.iterrows():
            match = opens[
                (opens["underlying"]   == close_row["underlying"]) &
                (opens["option_type"]  == close_row["option_type"]) &
                (opens["expiration"]   != close_row["expiration"])   # different expiry = roll
            ]
            if match.empty:
                continue

            roll_id = str(uuid.uuid4())
            df.loc[close_row.name, "roll_id"] = roll_id
            df.loc[match.index[0],  "roll_id"] = roll_id

    return df
```

---

## 6. Strategy tagger

```python
# src/ibkr_trades/strategy_tagger.py

def infer_strategy(row: dict) -> str | None:
    """
    Infers option strategy from trade record fields.
    Conservative rules only — ambiguous cases return 'other'.
    """
    if row.get("asset_type") != "OPT":
        return None
    if row.get("roll_id"):
        return "roll"

    qty   = row.get("quantity", 0)
    otype = row.get("option_type")
    oc    = row.get("open_close", "")

    if qty < 0 and otype == "CALL" and "O" in oc:
        return "covered_call"  # short call opening (assumes stock held — not verified here)
    if qty < 0 and otype == "PUT" and "O" in oc:
        return "csp"           # short put opening (cash-secured or margin — not verified)
    if qty > 0 and otype == "CALL" and "O" in oc:
        return "long_call"
    if qty > 0 and otype == "PUT" and "O" in oc:
        return "long_put"

    return "other"
```

---

## 7. Tracker builder — derive `options_tracker.csv` from open legs

```python
# src/ibkr_trades/tracker_builder.py

from pathlib import Path
import pandas as pd
from datetime import date

TRACKER_COLUMNS = [
    "symbol", "underlying", "option_type", "strike", "expiration",
    "quantity", "premium_received", "current_value", "unrealized_pnl",
    "dte", "trade_id", "roll_id", "strategy", "open_date",
]

def build_options_tracker(
    history_path: Path,
    tracker_path: Path,
) -> int:
    """
    Derives options_tracker.csv from trades_history.csv.
    Logic:
      - For each option contract, sum quantity across all opening (O) trades.
      - Subtract quantity from closing (C) trades.
      - Net quantity != 0 → position is open.
    Returns number of open legs written.
    """
    df = pd.read_csv(history_path, dtype={"trade_id": str})
    opts = df[df["asset_type"] == "OPT"].copy()

    match_key = ["underlying", "option_type", "strike", "expiration"]

    # Compute net open quantity per contract
    opts["signed_qty"] = opts.apply(
        lambda r: r["quantity"] if "O" in str(r["open_close"])
                  else -r["quantity"],
        axis=1,
    )
    net = opts.groupby(match_key)["signed_qty"].sum().reset_index()
    open_legs = net[net["signed_qty"].abs() > 0.001]

    if open_legs.empty:
        tracker_path.write_text(",".join(TRACKER_COLUMNS) + "\n")
        return 0

    # Enrich with metadata from the most recent opening trade per contract
    latest_open = (
        opts[opts["open_close"].str.contains("O", na=False)]
        .sort_values("datetime")
        .groupby(match_key)
        .last()
        .reset_index()
    )
    merged = open_legs.merge(latest_open, on=match_key, how="left")
    merged["quantity"]         = merged["signed_qty"]
    merged["premium_received"] = merged["proceeds"].abs()
    merged["current_value"]    = None   # populated at runtime by exit_monitor
    merged["unrealized_pnl"]   = None
    merged["dte"] = merged["expiration"].apply(
        lambda e: (date.fromisoformat(e) - date.today()).days
        if pd.notna(e) else None
    )
    merged["open_date"] = merged["date"]

    output = merged[TRACKER_COLUMNS]
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(tracker_path, index=False)
    return len(output)
```

---

## 8. CLI entry point

```python
# src/ibkr_trades/main.py
# Commands: backfill | sync | generate-tracker | full

# backfill  --flex PATH
# sync      (connects to IB Gateway)
# generate-tracker
# full      = sync + generate-tracker
```

---

## Justfile additions

```just
# One-time backfill from Flex Query XML export
# Export from IBKR: Reports → Activity → Flex Queries → All trades since inception
ibkr-backfill flex="data/ibkr/flex_export.xml":
    PYTHONPATH=src uv run python -m ibkr_trades.main backfill \
        --flex {{flex}} \
        --history data/ibkr/trades_history.csv
    @echo "✓ Backfill complete. Run 'just ibkr-generate-tracker' to rebuild options_tracker.csv"

# Fetch new trades from IB Gateway since last sync date
ibkr-sync:
    #!/usr/bin/env bash
    set -euo pipefail
    HOST=$(ip route show default | awk '{print $3}')
    PYTHONPATH=src uv run python -m ibkr_trades.main sync \
        --host "$HOST" --port 7496 \
        --history data/ibkr/trades_history.csv

# Rebuild options_tracker.csv from trade history (no network needed)
ibkr-generate-tracker:
    PYTHONPATH=src uv run python -m ibkr_trades.main generate-tracker \
        --history  data/ibkr/trades_history.csv \
        --tracker  options_tracker.csv \
        --backup-dir data/ibkr/

# Full flow: sync + generate-tracker (run daily alongside ibkr-positions)
ibkr-trades-daily:
    just ibkr-sync
    just ibkr-generate-tracker
    @echo "✓ options_tracker.csv rebuilt from live trade history"
```

Update `ibkr-positions` to call `ibkr-trades-daily` first:

```just
ibkr-positions output-dir="reports/output" host="" port="7496":
    #!/usr/bin/env bash
    just ibkr-trades-daily          # ← prepend: sync trades + rebuild tracker
    ...existing recipe...
```

---

## First-run guide (one-time setup)

```bash
# Step 1: Export Flex Query from IBKR web portal
# Flex Queries → Create → All Trades → Date range: account inception → today
# Format: XML → Run → Download → save as data/ibkr/flex_export.xml

# Step 2: Backfill
just ibkr-backfill flex=data/ibkr/flex_export.xml

# Step 3: Rebuild options_tracker.csv
just ibkr-generate-tracker

# Step 4: Verify
cat options_tracker.csv
# Expected: 4 open July options (AAPL CC, FSLY, PEP, SMR puts)

# Step 5: From now on, just ibkr-positions handles everything automatically
just ibkr-positions
```

---

## Tests (minimum 10)

```python
def test_flex_parser_returns_opt_and_stk_trades()
# XML with OPT + STK + DIV rows → only OPT and STK returned

def test_flex_parser_maps_put_call_correctly()
# putCall="P" → option_type="PUT"; putCall="C" → option_type="CALL"

def test_flex_parser_sets_source_to_flex()
# All records from Flex XML have source="flex"

def test_store_append_deduplicates_by_trade_id(tmp_path)
# Same trade_id written twice → only one row in output CSV

def test_store_append_returns_added_and_skipped_counts(tmp_path)
# 3 new + 2 duplicate → (3, 2)

def test_store_last_sync_date_returns_most_recent_date(tmp_path)
# History with dates 2026-06-01 and 2026-06-20 → returns 2026-06-20

def test_roll_detector_tags_same_day_close_open_pair()
# Close PEP P140 Jul + Open PEP P140 Aug same day → both get same roll_id

def test_roll_detector_does_not_tag_unrelated_trades()
# Close AAPL CC + Open PEP CSP → no roll_id assigned

def test_tracker_builder_shows_only_open_legs(tmp_path)
# History: open qty=-1 + close qty=+1 for same contract → not in tracker

def test_tracker_builder_correct_net_qty_for_partial_close(tmp_path)
# Open qty=-12, close qty=+6 → tracker shows qty=-6

def test_tracker_builder_archives_existing_manual_tracker(tmp_path)
# Existing options_tracker.csv is moved to backup before overwrite

def test_strategy_tagger_covered_call()
# qty=-1, option_type=CALL, open_close=O → strategy="covered_call"

def test_strategy_tagger_csp()
# qty=-1, option_type=PUT, open_close=O → strategy="csp"
```

---

## Verification

```bash
# 1. Tests (no network, no IB Gateway needed)
uv run pytest tests/ibkr_trades/ -v

# 2. Lint
uv run ruff check src/ibkr_trades/ tests/ibkr_trades/

# 3. Full backfill + tracker rebuild (offline, IB Gateway NOT needed)
just ibkr-backfill flex=data/ibkr/flex_export.xml
just ibkr-generate-tracker
diff options_tracker.csv <(head -5 options_tracker.csv)  # sanity check schema

# 4. Confirm July positions present
grep "260717" options_tracker.csv
# Expected: 4 rows (AAPL CC, FSLY P15, PEP P140, SMR P9)

# 5. Idempotency — run sync twice, row count unchanged
just ibkr-sync
COUNT_1=$(wc -l < data/ibkr/trades_history.csv)
just ibkr-sync
COUNT_2=$(wc -l < data/ibkr/trades_history.csv)
[ "$COUNT_1" -eq "$COUNT_2" ] && echo "✓ idempotent" || echo "✗ duplicate rows"

# 6. Full automated flow
just ibkr-positions
# Confirm options_tracker.csv rebuilt automatically before report generation
```

---

## Known limitations / follow-up

- `pnl_realized` is not populated by the incremental API fetcher (`reqExecutions`
  does not return P&L). It is populated by the Flex Query XML only. For incremental
  runs, `pnl_realized` will be null and must be treated as informational-only until
  the next Flex Query export or until a CommissionReport handler is added.
- `open_close` from `reqExecutions` is not always reliable for options.
  The tracker builder infers open/closed state from net quantity, which is more
  robust than trusting the `openCloseIndicator` field from the API.
- Roll detection uses same-day heuristic only. Same-week rolls (e.g., Monday
  close + Tuesday open) are not detected. A `window_days=1` parameter is available
  but not enabled by default to avoid false positives.
- The strategy tagger cannot distinguish a CSP (cash-secured) from a naked put —
  it does not verify that sufficient cash covers the assignment. That check lives
  in T02 (`cash_coverage`).
- STK trades are stored in history for future P&L accounting (T04 IRPF report)
  but are not written to `options_tracker.csv`, which is options-only.

# Task: Daily IBKR Snapshot History — Cumulative Performance Tracking

**Status:** Completed for point-in-time snapshot history
**Remaining:** True YTD collected-premium aggregation requires trade history;
it is not available from point-in-time open positions.
**Skill:** add-feature
**Scope:** `src/ibkr_positions/snapshot_store.py` (new), `justfile`
**Effort:** S
**Depends on:** T01, T02 (stable report structure before we start accumulating history)

---

## Context

Every `just ibkr-positions` run generates a fresh dated report but discards
the prior day's data. There is no time-series of account state. This makes it
impossible to answer:
- What was the NLV 30 days ago?
- How much premium was collected from short options this quarter?
- What is the realized P&L from covered calls vs cash-secured puts YTD?

The solution is a lightweight append-only store: after each `ibkr-positions` run,
append a compact JSON line to a history file. No database. No schema migrations.
One JSON line per day.

---

## Goal

After each `just ibkr-positions` run, persist a daily snapshot of the key
account metrics into `data/ibkr/history.jsonl` (newline-delimited JSON).
Add a `just ibkr-history` command that reads the history file and prints a
performance summary table.

---

## Outcome spec

When done, the following must be true:

1. `just ibkr-positions` appends one JSON line to `data/ibkr/history.jsonl`
   after a successful fetch (idempotent: if today's date already exists, update
   rather than duplicate).
2. Each line contains:
   ```json
   {
     "date": "2026-06-23",
     "nlv": 50000.00,
     "cash": 12000.00,
     "invested": 38000.00,
     "unrealized_pnl": 1200.00,
     "options_premium_received": 800.00,
     "options_current_value": -850.00,
     "options_pnl": -50.00,
     "stk_pnl": 1250.00,
     "margin_utilization": 0.25,
     "net_delta_approx": null
   }
   ```
   `net_delta_approx` is populated if T02 is available, otherwise null.
3. `just ibkr-history` reads `history.jsonl` and prints a markdown table
   to stdout with: date, NLV, cash, unrealized P&L, options P&L, options
   premium collected YTD.
4. `just ibkr-history days=30` limits the table to the last N days.
5. Running `just ibkr-positions` multiple times on the same day: last write wins
   (upsert by date).
6. `uv run pytest tests/ibkr_positions/test_snapshot_store.py` passes (≥5 tests).
7. `data/ibkr/history.jsonl` is gitignored (sensitive account data).

---

## Constraints

- JSONL only. No SQLite, no pandas required for writing.
  Reading with pandas is acceptable for the summary table.
- Append logic: read all lines, upsert current date entry, rewrite file.
  The file will have at most ~365 lines/year — rewriting is cheap.
- If the history file does not exist, create it.
- `net_delta_approx` is null if T02 is not yet implemented (graceful degradation).
- History file must be excluded from git (`data/ibkr/` → `.gitignore`).

---

## Key design

```
src/ibkr_positions/snapshot_store.py
```

```python
from pathlib import Path
import json
from datetime import date

HISTORY_PATH = Path("data/ibkr/history.jsonl")

def append_snapshot(portfolio: Portfolio, history_path: Path = HISTORY_PATH) -> None:
    """
    Upsert today's snapshot into the JSONL history file.
    """
    today = date.today().isoformat()
    snapshot = _build_snapshot(portfolio, today)

    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing entries, upsert today's
    entries: dict[str, dict] = {}
    if history_path.exists():
        for line in history_path.read_text().splitlines():
            entry = json.loads(line)
            entries[entry["date"]] = entry

    entries[today] = snapshot

    history_path.write_text(
        "\n".join(json.dumps(e) for e in entries.values()) + "\n"
    )


def load_history(history_path: Path = HISTORY_PATH, days: int | None = None) -> list[dict]:
    """
    Returns history entries sorted by date ascending.
    Optionally limited to the last `days` entries.
    """
    if not history_path.exists():
        return []
    entries = [json.loads(l) for l in history_path.read_text().splitlines() if l.strip()]
    entries.sort(key=lambda e: e["date"])
    if days is not None:
        entries = entries[-days:]
    return entries
```

Justfile:

```just
# Show IBKR account performance history
ibkr-history days="90":
    PYTHONPATH=src uv run python -m ibkr_positions.snapshot_store \
        --history data/ibkr/history.jsonl \
        --days {{days}}
```

Files to create/modify:
```
src/ibkr_positions/snapshot_store.py              ← NEW
src/ibkr_positions/main.py                        ← call append_snapshot() after report
tests/ibkr_positions/test_snapshot_store.py       ← NEW
.gitignore                                        ← add data/ibkr/
justfile                                          ← add ibkr-history recipe
```

---

## Output format (`just ibkr-history`)

```
IBKR Account History — last 30 days

| Date       | NLV ($)    | Cash ($)  | Unreal. P&L | OPT P&L  | Premium YTD |
|------------|-----------|-----------|-------------|----------|-------------|
| 2026-05-24 | 59,250.00 | 12,100.00 | +$1,840.00  | +$230.00 | $892.00     |
| 2026-06-23 | 62,406.13 | 14,023.21 | +$3,075.06  | -$63.94  | $1,278.30   |

NLV change (30d): +$3,156.13 (+5.33%)
Premium collected YTD: $1,278.30
```

---

## Tests (minimum 5)

```python
def test_first_snapshot_creates_file(tmp_path)
# No history file exists; append_snapshot() creates it with 1 line

def test_second_snapshot_on_same_day_upserts(tmp_path)
# Two calls with same date → file still has 1 line (last write wins)

def test_second_snapshot_on_different_day_appends(tmp_path)
# Entry for 2026-06-22 then 2026-06-23 → file has 2 lines

def test_load_history_returns_entries_sorted_by_date(tmp_path)
# Write entries out of order; load_history returns them sorted ascending

def test_load_history_days_limit(tmp_path)
# 10 entries, days=3 → returns last 3 only
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/ibkr_positions/test_snapshot_store.py -v

# 2. Live run — must write to history
just ibkr-positions
cat data/ibkr/history.jsonl | python -m json.tool | head -30

# 3. History report
just ibkr-history days=30

# 4. Idempotency — run twice same day, confirm only 1 entry for today
just ibkr-positions
wc -l data/ibkr/history.jsonl  # count should not increase

# 5. Lint
uv run ruff check src/ibkr_positions/snapshot_store.py \
  tests/ibkr_positions/test_snapshot_store.py
```

---

## Known limitations / follow-up

- Does not capture realized P&L (closed trades). That is handled by T04 (IRPF report).
- The history file is a flat JSONL — no indexing, no query engine. For anything
  beyond ~2 years of daily data, a SQLite store (future task) would be more
  appropriate.
- `options_premium_received` is the sum of cost_basis across all open short option
  legs — it is a snapshot of unrealized premium, not cumulative collected premium.
  Cumulative collected premium requires trade history (T04 scope).

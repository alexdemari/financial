# Task: Auto-Reconcile `options_tracker.csv` Against Live IBKR Positions

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/ibkr_positions/reconciler.py` (new), `justfile`
**Effort:** S
**Depends on:** T01 (options_tracker_live.csv must exist before reconciliation)

---

## Context

`options_tracker.csv` is the manual record of all options positions: entries,
premiums received, exit dates. It is the historical source of truth and feeds
both the exit monitor and future P&L accounting.

After T01, the live IBKR snapshot writes `options_tracker_live.csv` with current
open positions. The two files can diverge when:
- A position is closed in IBKR but not updated in the manual CSV.
- A new position is opened in IBKR but not yet added to the manual CSV.
- Quantity changes (e.g., partial close of the SMR ×12 position).

This task adds a reconciliation step that diffs the two files and prints a clear
action list — without auto-modifying anything.

---

## Goal

Create `ibkr_positions.reconciler` that compares the live snapshot against the
manual tracker and produces a structured diff report, printed to stdout and
optionally written to `reports/output/reconciliation_YYYY-MM-DD.md`.

---

## Outcome spec

When done, the following must be true:

1. `just ibkr-reconcile` runs without error and prints a diff report.
2. The diff identifies three categories:
   - **LIVE_ONLY**: position exists in IBKR but not in `options_tracker.csv`
     → suggests: "Add to tracker"
   - **TRACKER_ONLY**: position exists in tracker (open, no exit_date) but not
     in IBKR → suggests: "Mark as closed or verify"
   - **QUANTITY_MISMATCH**: position exists in both but quantities differ
     → shows: tracker qty vs live qty
3. Positions matched by: `(underlying, option_type, strike, expiration)` tuple.
4. If no divergence, prints: `✓ options_tracker.csv is in sync with IBKR.`
5. `uv run pytest tests/ibkr_positions/test_reconciler.py` passes (≥5 tests).
6. No file is written or modified automatically — reconciler is read-only output.

---

## Constraints

- Reconciler is read-only. It never modifies `options_tracker.csv` or any live file.
- No network calls. Reads two local CSV files only.
- Output is always human-readable (no JSON/binary output).
- Match key is `(underlying, option_type, strike, expiration)` — not `symbol`,
  because IBKR symbol strings differ from tracker format.
- Positions in `options_tracker.csv` with a non-empty `exit_date` are considered
  closed and excluded from the diff.

---

## Key design

```
src/ibkr_positions/reconciler.py
```

```python
from dataclasses import dataclass
from pathlib import Path
import pandas as pd

MatchKey = tuple[str, str, float, str]  # (underlying, option_type, strike, expiration)

@dataclass
class ReconciliationResult:
    live_only: list[dict]        # in IBKR, not in tracker
    tracker_only: list[dict]     # in tracker (open), not in IBKR
    quantity_mismatch: list[dict] # in both, quantities differ
    in_sync: bool

def reconcile(
    live_csv: Path,
    tracker_csv: Path,
) -> ReconciliationResult:
    ...

def format_report(result: ReconciliationResult) -> str:
    ...
```

CLI / entry point — extend `ibkr_positions.main` with an optional `--reconcile` flag:

```bash
just ibkr-reconcile
# → runs just ibkr-positions first, then reconciler
```

Justfile:

```just
ibkr-reconcile:
    #!/usr/bin/env bash
    set -euo pipefail
    HOST=$(ip route show default | awk '{print $3}')
    PYTHONPATH=src uv run python -m ibkr_positions.main \
        --output-dir reports/output \
        --host "$HOST" \
        --port 7496
    PYTHONPATH=src uv run python -m ibkr_positions.reconciler \
        --live   reports/output/options_tracker_live.csv \
        --tracker options_tracker.csv \
        --output  reports/output/reconciliation_$(date +%Y-%m-%d).md
```

Files to create/modify:
```
src/ibkr_positions/reconciler.py                      ← NEW
tests/ibkr_positions/test_reconciler.py               ← NEW
justfile                                              ← add ibkr-reconcile recipe
```

---

## Tests (minimum 5)

```python
def test_in_sync_when_both_csvs_match()
# same 2 positions in both → in_sync=True, all lists empty

def test_live_only_detected()
# position in live CSV not present in tracker → live_only has 1 entry

def test_tracker_only_detected()
# open position in tracker not present in live → tracker_only has 1 entry

def test_closed_tracker_positions_excluded()
# tracker row with exit_date set → excluded from diff (not flagged as tracker_only)

def test_quantity_mismatch_detected()
# same match key but tracker qty=12, live qty=6 → quantity_mismatch has 1 entry
```

---

## Verification

```bash
# 1. Tests (no network required)
uv run pytest tests/ibkr_positions/test_reconciler.py -v

# 2. Live run (IB Gateway must be running)
just ibkr-reconcile

# Expected output if 4 July positions match tracker:
# ✓ options_tracker.csv is in sync with IBKR.

# Expected if SMR qty changed:
# QUANTITY MISMATCH
# SMR PUT $9.00 exp 2026-07-17: tracker=12 | live=6

# 3. Lint
uv run ruff check src/ibkr_positions/reconciler.py \
  tests/ibkr_positions/test_reconciler.py
```

---

## Known limitations / follow-up

- Does not auto-update `options_tracker.csv`. A future task (T-backfill) could
  add a `--apply` flag to write suggested additions for confirmed positions.
- Does not compare `premium_received` — only structural position identity and quantity.

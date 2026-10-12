"""Read the latest immutable B3 custody snapshot for the local dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from b3_importer.positions_store import latest_snapshot
from web.readers.common import PROJECT_ROOT

B3_POSITIONS_DIR = PROJECT_ROOT / "data/b3/positions"
B3_RECONCILIATION_REPORT = PROJECT_ROOT / "reports/b3_reconciliation_latest.md"
STALE_AFTER_DAYS = 7


def read_b3_positions(reference_date: date) -> dict[str, Any]:
    """Return latest B3 snapshot, freshness, and reconciliation metadata."""
    snapshot = latest_snapshot(B3_POSITIONS_DIR)
    if snapshot is None:
        return _empty_result("no_data", "Run: just b3-positions-import")
    try:
        frame = pd.read_csv(snapshot)
    except pd.errors.EmptyDataError:
        return _empty_result("invalid", "B3 snapshot is empty")
    rows = [
        {key: None if pd.isna(value) else value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    as_of = str(rows[0]["as_of"]) if rows else None
    try:
        stale = (
            (reference_date - date.fromisoformat(as_of)).days > STALE_AFTER_DAYS
            if as_of
            else True
        )
    except ValueError:
        stale = True
    included = [row for row in rows if _truthy(row.get("included_in_total"))]
    return {
        "status": "ok",
        "hint": None,
        "total_brl": sum(_number(row.get("value_brl")) for row in included),
        "positions": rows,
        "as_of": as_of,
        "stale": stale,
        "snapshot_path": _relative(snapshot),
        "reconciliation": _reconciliation_status(snapshot),
    }


def _empty_result(status: str, hint: str) -> dict[str, Any]:
    return {
        "status": status,
        "hint": hint,
        "total_brl": 0.0,
        "positions": [],
        "as_of": None,
        "stale": True,
        "reconciliation": _reconciliation_status(),
    }


def _reconciliation_status(snapshot: Path | None = None) -> dict[str, Any]:
    if not B3_RECONCILIATION_REPORT.exists():
        return {"status": "not_run", "report_path": None}
    content = B3_RECONCILIATION_REPORT.read_text(encoding="utf-8")
    if snapshot is not None and f"Snapshot: `{snapshot.name}`" not in content:
        return {
            "status": "outdated",
            "report_path": _relative(B3_RECONCILIATION_REPORT),
        }
    statuses = ("missing_btg", "excess_btg", "quantity_mismatch")
    issues = any(f"| {status} | 0 |" not in content for status in statuses)
    return {
        "status": "issues" if issues else "in_sync",
        "report_path": _relative(B3_RECONCILIATION_REPORT),
    }


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _truthy(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _number(value: object) -> float:
    try:
        return float(value) if value is not None and not pd.isna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0

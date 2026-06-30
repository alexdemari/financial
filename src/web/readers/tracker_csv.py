from __future__ import annotations

import csv

from web.readers.common import PROJECT_ROOT, file_mtime

TRACKER_PATH = PROJECT_ROOT / "options_tracker.csv"


def read_open_legs() -> dict:
    if not TRACKER_PATH.exists():
        return {"rows": [], "last_updated": None}
    with TRACKER_PATH.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, delimiter=";"))
    open_rows = [row for row in rows if not row.get("close_date")]
    return {"rows": open_rows, "last_updated": file_mtime(TRACKER_PATH)}

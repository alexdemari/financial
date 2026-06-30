from __future__ import annotations

import csv

from web.readers.common import PROJECT_ROOT, file_mtime

SCAN_PATH = PROJECT_ROOT / "reports/market_scanner/scan_daily.csv"


def read_scan(limit: int = 20) -> dict:
    if not SCAN_PATH.exists():
        return {"rows": [], "last_updated": None}
    with SCAN_PATH.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    candidates = [row for row in rows if row.get("action_bucket") == "candidate"]
    candidates.sort(
        key=lambda row: float(row.get("consistency_score") or 0), reverse=True
    )
    return {"rows": candidates[:limit], "last_updated": file_mtime(SCAN_PATH)}

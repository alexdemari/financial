from __future__ import annotations

import json
from dataclasses import dataclass

from web.readers.common import PROJECT_ROOT, file_mtime

HISTORY_PATH = PROJECT_ROOT / "data/ibkr/history.jsonl"


@dataclass(frozen=True)
class AccountSnapshot:
    nlv: float
    cash: float
    invested: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    margin_utilization: float | None
    net_delta_approx: float | None
    as_of: str
    last_updated: str


def read_history(days: int = 90) -> list[dict]:
    if days <= 0:
        raise ValueError("days must be greater than zero")
    if not HISTORY_PATH.exists():
        return []
    entries = [
        json.loads(line)
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    entries.sort(key=lambda entry: entry["date"])
    return entries[-days:]


def read_account_snapshot() -> AccountSnapshot | None:
    entries = read_history(days=1)
    if not entries:
        return None
    entry = entries[0]
    invested = _float(entry.get("invested"))
    unrealized_pnl = _float(entry.get("unrealized_pnl"))
    return AccountSnapshot(
        nlv=_float(entry.get("nlv")),
        cash=_float(entry.get("cash")),
        invested=invested,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl / abs(invested) if invested else 0.0,
        margin_utilization=_optional_float(entry.get("margin_utilization")),
        net_delta_approx=_optional_float(entry.get("net_delta_approx")),
        as_of=str(entry["date"]),
        last_updated=file_mtime(HISTORY_PATH),
    )


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: object) -> float | None:
    return None if value is None else _float(value)

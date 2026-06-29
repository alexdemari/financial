from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd

from ibkr_trades.models import TradeRecord

HISTORY_PATH = Path("data/ibkr/trades_history.csv")

_DTYPES = {"trade_id": str, "roll_id": str, "strategy": str}


def load_history(path: Path = HISTORY_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=_DTYPES)


def append_trades(
    new_records: list[TradeRecord],
    path: Path = HISTORY_PATH,
) -> tuple[int, int]:
    """Append new_records to history CSV, deduplicating by trade_id.

    Returns (added_count, skipped_count).
    """
    # Dedup within the incoming batch first (preserves first occurrence)
    seen: dict[str, TradeRecord] = {}
    for r in new_records:
        seen.setdefault(r.trade_id, r)
    deduped = list(seen.values())

    existing = load_history(path)
    existing_ids: set[str] = (
        set(existing["trade_id"].astype(str)) if not existing.empty else set()
    )

    new_rows = [r for r in deduped if r.trade_id not in existing_ids]
    skipped = len(new_records) - len(new_rows)

    if not new_rows:
        return 0, skipped

    new_df = pd.DataFrame([asdict(r) for r in new_rows])
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values(["date", "datetime"]).reset_index(drop=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)

    return len(new_rows), skipped


def last_sync_date(path: Path = HISTORY_PATH) -> date | None:
    """Return the most recent trade date in history, or None if empty."""
    df = load_history(path)
    if df.empty or "date" not in df.columns:
        return None
    return pd.to_datetime(df["date"]).max().date()

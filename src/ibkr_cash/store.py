from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ibkr_cash.models import CashTransaction, NavChange

CASH_TRANSACTIONS_PATH = Path("data/ibkr/cash_transactions.csv")
NAV_CHANGES_PATH = Path("data/ibkr/nav_changes.csv")

_CASH_TX_KEY = ["date", "type", "amount", "description"]
_NAV_KEY = ["from_date", "to_date"]


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _upsert(
    new_rows: pd.DataFrame, path: Path, key_columns: list[str]
) -> tuple[int, int]:
    """Upsert new_rows into the CSV at path, keyed by key_columns.

    Returns (added_count, updated_count). Rows matching an existing key are
    replaced with the new values; unmatched rows are appended.
    """
    existing = _load(path)

    if existing.empty:
        added, updated = len(new_rows), 0
        combined = new_rows
    else:
        existing_keys = set(existing[key_columns].itertuples(index=False, name=None))
        new_keys = set(new_rows[key_columns].itertuples(index=False, name=None))
        added = len(new_keys - existing_keys)
        updated = len(new_keys & existing_keys)

        kept_existing = existing[
            ~existing[key_columns]
            .apply(tuple, axis=1)
            .isin(new_rows[key_columns].apply(tuple, axis=1))
        ]
        combined = pd.concat([kept_existing, new_rows], ignore_index=True)

    combined = combined.sort_values(key_columns).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)
    return added, updated


def load_cash_transactions(path: Path = CASH_TRANSACTIONS_PATH) -> pd.DataFrame:
    return _load(path)


def upsert_cash_transactions(
    records: list[CashTransaction], path: Path = CASH_TRANSACTIONS_PATH
) -> tuple[int, int]:
    if not records:
        return 0, 0
    df = pd.DataFrame([asdict(r) for r in records]).drop_duplicates(subset=_CASH_TX_KEY)
    return _upsert(df, path, _CASH_TX_KEY)


def load_nav_changes(path: Path = NAV_CHANGES_PATH) -> pd.DataFrame:
    return _load(path)


def upsert_nav_changes(
    records: list[NavChange], path: Path = NAV_CHANGES_PATH
) -> tuple[int, int]:
    if not records:
        return 0, 0
    df = pd.DataFrame([asdict(r) for r in records]).drop_duplicates(subset=_NAV_KEY)
    return _upsert(df, path, _NAV_KEY)

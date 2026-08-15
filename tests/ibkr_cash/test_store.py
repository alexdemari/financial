from __future__ import annotations

from pathlib import Path

from ibkr_cash.models import CashTransaction, NavChange
from ibkr_cash.store import (
    load_cash_transactions,
    load_nav_changes,
    upsert_cash_transactions,
    upsert_nav_changes,
)

_TX = CashTransaction(
    date="2026-01-05",
    type="Deposits/Withdrawals",
    amount=5000.0,
    currency="USD",
    description="DISBURSEMENT",
)
_NAV = NavChange(
    from_date="2026-01-01",
    to_date="2026-01-31",
    starting_value=100000.0,
    ending_value=106063.54,
    deposits_withdrawals=5000.0,
    net_trades=1063.54,
)


def test_upsert_cash_transactions_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "cash_transactions.csv"

    added1, updated1 = upsert_cash_transactions([_TX], path)
    assert (added1, updated1) == (1, 0)

    added2, updated2 = upsert_cash_transactions([_TX], path)
    assert (added2, updated2) == (0, 1)

    df = load_cash_transactions(path)
    assert len(df) == 1


def test_upsert_nav_changes_overwrites_same_period(tmp_path: Path) -> None:
    path = tmp_path / "nav_changes.csv"

    upsert_nav_changes([_NAV], path)
    revised = NavChange(**{**_NAV.__dict__, "ending_value": 107000.0})
    added, updated = upsert_nav_changes([revised], path)

    assert (added, updated) == (0, 1)
    df = load_nav_changes(path)
    assert len(df) == 1
    assert df.iloc[0]["ending_value"] == 107000.0

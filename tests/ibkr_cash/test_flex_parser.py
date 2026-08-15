from __future__ import annotations

from pathlib import Path

import pytest

from ibkr_cash.flex_parser import parse_cash_transactions, parse_nav_changes

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "flex_cash_transactions.xml"
)


def test_parse_cash_transactions() -> None:
    records = parse_cash_transactions(FIXTURE)

    assert len(records) == 3
    deposit = records[0]
    assert deposit.date == "2026-01-05"
    assert deposit.type == "Deposits/Withdrawals"
    assert deposit.amount == 5000.00
    assert deposit.currency == "USD"

    dividend = records[1]
    assert dividend.type == "Dividends"
    assert dividend.amount == 67.75

    interest = records[2]
    assert interest.type == "Broker Interest Paid"
    assert interest.amount == -4.21


def test_parse_nav_changes() -> None:
    records = parse_nav_changes(FIXTURE)

    assert len(records) == 1
    nav = records[0]
    assert nav.from_date == "2026-01-01"
    assert nav.to_date == "2026-01-31"
    assert nav.starting_value == 100000.00
    assert nav.ending_value == 106063.54
    assert nav.deposits_withdrawals == 5000.00
    assert nav.net_trades == pytest.approx(1063.54)


def test_nav_reconciliation_holds() -> None:
    for nav in parse_nav_changes(FIXTURE):
        computed = nav.starting_value + nav.deposits_withdrawals + nav.net_trades
        assert abs(computed - nav.ending_value) < 1e-6

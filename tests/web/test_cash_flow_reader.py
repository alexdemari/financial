from __future__ import annotations

import pandas as pd

from web.readers import cash_flow_reader


def _set_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(cash_flow_reader, "CASH_TRANSACTIONS", tmp_path / "cash.csv")
    monkeypatch.setattr(cash_flow_reader, "NAV_CHANGES", tmp_path / "nav.csv")


def test_read_cash_transactions_returns_empty_when_file_missing(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    assert cash_flow_reader.read_cash_transactions() == []


def test_read_cash_transactions_sorted_descending(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "type": "Deposits/Withdrawals",
                "amount": 10,
                "currency": "USD",
                "description": "a",
            },
            {
                "date": "2026-02-01",
                "type": "Dividends",
                "amount": 2,
                "currency": "USD",
                "description": "b",
            },
        ]
    ).to_csv(cash_flow_reader.CASH_TRANSACTIONS, index=False)
    assert [row["date"] for row in cash_flow_reader.read_cash_transactions()] == [
        "2026-02-01",
        "2026-01-01",
    ]


def test_reconciliation_flags_mismatch_beyond_tolerance(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "from_date": "2026-01-01",
                "to_date": "2026-01-31",
                "starting_value": 100,
                "ending_value": 120,
                "deposits_withdrawals": 5,
                "net_trades": 10,
            }
        ]
    ).to_csv(cash_flow_reader.NAV_CHANGES, index=False)
    row = cash_flow_reader.read_nav_reconciliation()[0]
    assert row["reconciles"] is False
    assert row["diff"] == -5.0


def test_reconciliation_passes_within_tolerance(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "from_date": "2026-01-01",
                "to_date": "2026-01-31",
                "starting_value": 100,
                "ending_value": 115.5,
                "deposits_withdrawals": 5,
                "net_trades": 10.2,
            }
        ]
    ).to_csv(cash_flow_reader.NAV_CHANGES, index=False)
    assert cash_flow_reader.read_nav_reconciliation()[0]["reconciles"] is True


def test_cumulative_contributed_is_running_sum(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "type": "Deposits/Withdrawals",
                "amount": -3,
                "currency": "USD",
                "description": "withdrawal",
            },
            {
                "date": "2026-01-01",
                "type": "Deposits/Withdrawals",
                "amount": 10,
                "currency": "USD",
                "description": "deposit",
            },
            {
                "date": "2026-01-03",
                "type": "Dividends",
                "amount": 2,
                "currency": "USD",
                "description": "dividend",
            },
        ]
    ).to_csv(cash_flow_reader.CASH_TRANSACTIONS, index=False)
    assert cash_flow_reader.read_cumulative_contributed() == [
        {"date": "2026-01-01", "currency": "USD", "contributed": 10.0},
        {"date": "2026-01-02", "currency": "USD", "contributed": 7.0},
    ]


def test_cumulative_contributed_tracks_currencies_separately(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "type": "Deposits/Withdrawals",
                "amount": 10,
                "currency": "USD",
                "description": "deposit",
            },
            {
                "date": "2026-01-01",
                "type": "Deposits/Withdrawals",
                "amount": 50000,
                "currency": "BRL",
                "description": "deposit",
            },
            {
                "date": "2026-01-02",
                "type": "Deposits/Withdrawals",
                "amount": 5,
                "currency": "USD",
                "description": "deposit",
            },
        ]
    ).to_csv(cash_flow_reader.CASH_TRANSACTIONS, index=False)
    rows = cash_flow_reader.read_cumulative_contributed()
    usd_rows = [row for row in rows if row["currency"] == "USD"]
    brl_rows = [row for row in rows if row["currency"] == "BRL"]
    assert [row["contributed"] for row in usd_rows] == [10.0, 15.0]
    assert [row["contributed"] for row in brl_rows] == [50000.0]


def test_read_cash_transactions_skips_non_numeric_amount(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "type": "Deposits/Withdrawals",
                "amount": "10",
                "currency": "USD",
                "description": "a",
            },
            {
                "date": "2026-01-02",
                "type": "Deposits/Withdrawals",
                "amount": "N/A",
                "currency": "USD",
                "description": "corrupt",
            },
        ]
    ).to_csv(cash_flow_reader.CASH_TRANSACTIONS, index=False)
    rows = cash_flow_reader.read_cash_transactions()
    assert len(rows) == 1
    assert rows[0]["amount"] == 10.0

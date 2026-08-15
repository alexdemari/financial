from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ibkr_cash.models import CashTransaction, NavChange


def _format_date(s: str | None) -> str:
    """Normalize IBKR's yyyymmdd / yyyymmdd;hhmmss / yyyy-mm-dd to yyyy-mm-dd."""
    if not s:
        return ""
    s = s.strip().split(";")[0]
    if len(s) == 8 and "-" not in s:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10]


def _float(s: str | None, default: float = 0.0) -> float:
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def parse_cash_transactions(path: Path) -> list[CashTransaction]:
    """Parse IBKR Flex Query XML export. Returns all <CashTransaction> rows."""
    tree = ET.parse(path)
    root = tree.getroot()
    records: list[CashTransaction] = []

    for element in root.iter("CashTransaction"):
        date_str = element.get("dateTime") or element.get("reportDate") or ""
        records.append(
            CashTransaction(
                date=_format_date(date_str),
                type=element.get("type", ""),
                amount=_float(element.get("amount")),
                currency=element.get("currency", ""),
                description=element.get("description", ""),
            )
        )

    return records


def parse_nav_changes(path: Path) -> list[NavChange]:
    """Parse IBKR Flex Query XML export. Returns all <ChangeInNAV> rows."""
    tree = ET.parse(path)
    root = tree.getroot()
    records: list[NavChange] = []

    for element in root.iter("ChangeInNAV"):
        # A <ChangeInNAV> row carries the actual figures as attributes; a
        # wrapper (some IBKR statements nest per-currency rows inside one)
        # doesn't, and would otherwise parse into a bogus all-zero record.
        if element.get("startingValue") is None or element.get("endingValue") is None:
            continue

        starting_value = _float(element.get("startingValue"))
        ending_value = _float(element.get("endingValue"))
        deposits_withdrawals = _float(element.get("depositsWithdrawals")) or (
            _float(element.get("deposits")) + _float(element.get("withdrawals"))
        )
        net_trades = ending_value - starting_value - deposits_withdrawals

        records.append(
            NavChange(
                from_date=_format_date(
                    element.get("fromDate") or element.get("startDate")
                ),
                to_date=_format_date(element.get("toDate") or element.get("endDate")),
                starting_value=starting_value,
                ending_value=ending_value,
                deposits_withdrawals=deposits_withdrawals,
                net_trades=net_trades,
            )
        )

    return records

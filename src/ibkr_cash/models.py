from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CashTransaction:
    date: str  # yyyy-mm-dd
    type: str  # "Deposits/Withdrawals", "Broker Interest Paid", "Dividends", etc.
    amount: float
    currency: str
    description: str


@dataclass
class NavChange:
    from_date: str  # yyyy-mm-dd
    to_date: str  # yyyy-mm-dd
    starting_value: float
    ending_value: float
    deposits_withdrawals: float
    # Catch-all for trading P&L, dividends, interest, and fees: defined as the
    # remainder so starting_value + deposits_withdrawals + net_trades ==
    # ending_value holds by construction, not by enumerating every IBKR field.
    net_trades: float

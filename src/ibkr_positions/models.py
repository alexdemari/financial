from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    symbol: str
    asset_type: str  # STK | ETF | OPT | CASH
    quantity: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    currency: str
    expiration: str | None = None  # YYYY-MM-DD
    strike: float | None = None
    option_type: str | None = None  # CALL | PUT
    underlying: str | None = None
    delta: float | None = None
    underlying_price: float | None = None  # populated for options when available


@dataclass(frozen=True)
class CashBalance:
    currency: str
    balance: float
    settled_cash: float


@dataclass(frozen=True)
class AccountSummary:
    net_liquidation: float
    total_cash: float
    buying_power: float
    initial_margin: float
    maintenance_margin: float
    excess_liquidity: float
    leverage: float | None = None


@dataclass(frozen=True)
class Portfolio:
    account_id: str
    as_of: str  # ISO datetime string
    summary: AccountSummary
    cash: list[CashBalance]
    positions: list[Position]

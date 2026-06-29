from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class TradeRecord:
    trade_id: str
    date: date
    datetime: str
    symbol: str
    underlying: str
    asset_type: str  # STK | OPT | ETF | CASH
    option_type: str | None  # CALL | PUT | None
    strike: float | None
    expiration: str | None  # YYYY-MM-DD
    quantity: float  # positive=buy, negative=sell
    price: float
    proceeds: float
    commission: float
    pnl_realized: float | None
    currency: str
    open_close: str  # O | C | O;C
    source: str  # flex | api
    roll_id: str | None = None
    strategy: str | None = None

"""Domain records persisted by :mod:`crypto_trades`."""

from dataclasses import asdict, dataclass


@dataclass
class CryptoTrade:
    trade_id: str
    date: str
    datetime: str
    trade_type: str
    asset: str
    quantity: float
    price_usdt: float
    total_usdt: float
    fee_amount: float
    fee_currency: str
    fee_value_brl: float
    value_brl_binance: float
    ptax_bcb: float | None = None
    value_brl_ptax: float = 0.0
    source: str = "export"
    order_type: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class EarnRecord:
    trade_id: str
    date: str
    asset: str
    quantity: float
    value_brl_binance: float
    ptax_bcb: float | None = None
    value_brl_ptax: float = 0.0
    earn_type: str = ""
    source: str = "export"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AssetCostBasis:
    asset: str
    quantity: float = 0.0
    avg_cost_usdt: float = 0.0
    avg_cost_brl_ptax: float = 0.0
    total_invested_brl: float = 0.0
    trades_count: int = 0

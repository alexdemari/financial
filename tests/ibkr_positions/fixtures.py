"""Mock ib_insync objects for IBKRClient tests."""
from collections import namedtuple
from unittest.mock import MagicMock

# Minimal namedtuples mirroring ib_insync structures
AccountValue = namedtuple("AccountValue", "account tag value currency modelCode")
PortfolioItem = namedtuple(
    "PortfolioItem",
    "contract position marketValue averageCost unrealizedPNL realizedPNL account",
)


def _make_stock_contract(symbol: str = "AAPL", currency: str = "USD") -> MagicMock:
    c = MagicMock()
    c.secType = "STK"
    c.symbol = symbol
    c.localSymbol = symbol
    c.currency = currency
    c.lastTradeDateOrContractMonth = ""
    c.strike = 0.0
    c.right = ""
    return c


def _make_option_contract(
    symbol: str = "PEP",
    local_symbol: str = "PEP   270115P00140000",
    expiry: str = "20270115",
    strike: float = 140.0,
    right: str = "P",
    currency: str = "USD",
) -> MagicMock:
    c = MagicMock()
    c.secType = "OPT"
    c.symbol = symbol
    c.localSymbol = local_symbol
    c.currency = currency
    c.lastTradeDateOrContractMonth = expiry
    c.strike = strike
    c.right = right
    return c


# Account values covering summary + cash balance tags
MOCK_ACCOUNT_VALUES = [
    AccountValue("U1234567", "NetLiquidation", "50000.0", "USD", ""),
    AccountValue("U1234567", "TotalCashValue", "10000.0", "USD", ""),
    AccountValue("U1234567", "BuyingPower", "20000.0", "USD", ""),
    AccountValue("U1234567", "InitMarginReq", "5000.0", "USD", ""),
    AccountValue("U1234567", "MaintMarginReq", "3000.0", "USD", ""),
    AccountValue("U1234567", "ExcessLiquidity", "45000.0", "USD", ""),
    AccountValue("U1234567", "CashBalance", "10000.0", "USD", ""),
    AccountValue("U1234567", "SettledCash", "9800.0", "USD", ""),
    AccountValue("U1234567", "CashBalance", "5000.0", "BRL", ""),
    # BASE currency entry — should be filtered by caller if needed
    AccountValue("U1234567", "CashBalance", "10000.0", "BASE", ""),
]

MOCK_PORTFOLIO_ITEMS = [
    PortfolioItem(
        contract=_make_stock_contract("AAPL"),
        position=100.0,
        marketValue=18000.0,
        averageCost=150.0,
        unrealizedPNL=3000.0,
        realizedPNL=0.0,
        account="U1234567",
    ),
    PortfolioItem(
        contract=_make_option_contract(),
        position=-1.0,
        marketValue=-286.0,
        averageCost=2.86,
        unrealizedPNL=0.0,
        realizedPNL=0.0,
        account="U1234567",
    ),
]

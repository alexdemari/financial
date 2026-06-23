from __future__ import annotations

import logging
from datetime import UTC, datetime

from ib_insync import IB, PortfolioItem

from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position

logger = logging.getLogger(__name__)

_GATEWAY_NOT_RUNNING = (
    "Error: IB Gateway is not running on {host}:{port}\n"
    "Ensure IB Gateway is open, API is enabled on port {port}, and WSL access is allowed."
)


class IBKRConnectionError(RuntimeError):
    pass


class IBKRClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7496,
        client_id: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id

    def get_portfolio(self) -> Portfolio:
        ib = IB()
        try:
            ib.connect(
                self._host,
                self._port,
                clientId=self._client_id,
                readonly=True,
                timeout=10,
            )
        except (ConnectionRefusedError, OSError, TimeoutError) as exc:
            raise IBKRConnectionError(
                _GATEWAY_NOT_RUNNING.format(host=self._host, port=self._port)
            ) from exc

        try:
            accounts = ib.managedAccounts()
            if not accounts:
                raise IBKRConnectionError("No accounts returned from IB Gateway")
            account_id = accounts[0]

            summary = _parse_account_summary(ib, account_id)
            cash = _parse_cash_balances(ib, account_id)
            positions = _parse_positions(ib, account_id)

            return Portfolio(
                account_id=account_id,
                as_of=datetime.now(UTC).isoformat(),
                summary=summary,
                cash=cash,
                positions=positions,
            )
        finally:
            ib.disconnect()


def _parse_account_summary(ib: IB, account_id: str) -> AccountSummary:
    values: dict[str, float] = {}
    for av in ib.accountValues():
        if av.account != account_id or not av.currency:
            continue
        try:
            values.setdefault(av.tag, float(av.value))
        except (ValueError, TypeError):
            pass

    nlv = values.get("NetLiquidation", 0.0)
    initial_margin = values.get("InitMarginReq", 0.0)
    return AccountSummary(
        net_liquidation=nlv,
        total_cash=values.get("TotalCashValue", 0.0),
        buying_power=values.get("BuyingPower", 0.0),
        initial_margin=initial_margin,
        maintenance_margin=values.get("MaintMarginReq", 0.0),
        excess_liquidity=values.get("ExcessLiquidity", 0.0),
        leverage=initial_margin / nlv if nlv > 0 else None,
    )


def _parse_cash_balances(ib: IB, account_id: str) -> list[CashBalance]:
    cash_by_currency: dict[str, float] = {}
    settled_by_currency: dict[str, float] = {}

    for av in ib.accountValues():
        if av.account != account_id or not av.currency:
            continue
        try:
            if av.tag == "CashBalance":
                cash_by_currency[av.currency] = float(av.value)
            elif av.tag == "SettledCash":
                settled_by_currency[av.currency] = float(av.value)
        except (ValueError, TypeError):
            pass

    return [
        CashBalance(
            currency=currency,
            balance=balance,
            settled_cash=settled_by_currency.get(currency, 0.0),
        )
        for currency, balance in cash_by_currency.items()
    ]


def _parse_positions(ib: IB, account_id: str) -> list[Position]:
    positions: list[Position] = []
    for item in ib.portfolio():
        if item.account != account_id:
            continue
        try:
            positions.append(_parse_portfolio_item(item))
        except Exception as exc:
            logger.debug("Skipping position %s: %s", item.contract.symbol, exc)
    return positions


def _parse_portfolio_item(item: PortfolioItem) -> Position:
    contract = item.contract
    asset_type = str(contract.secType).upper()

    expiration: str | None = None
    raw_expiry = getattr(contract, "lastTradeDateOrContractMonth", None)
    if raw_expiry:
        expiration = _format_expiry(str(raw_expiry))

    option_type: str | None = None
    right = getattr(contract, "right", None)
    if right in ("C", "CALL"):
        option_type = "CALL"
    elif right in ("P", "PUT"):
        option_type = "PUT"

    strike_raw = getattr(contract, "strike", None)
    strike: float | None = float(strike_raw) if strike_raw else None
    if strike == 0.0:
        strike = None

    if asset_type == "OPT":
        symbol = getattr(contract, "localSymbol", None) or contract.symbol
        underlying = contract.symbol
    else:
        symbol = contract.symbol
        underlying = None

    quantity = float(item.position)
    avg_cost = float(item.averageCost) if item.averageCost else 0.0
    cost_basis = avg_cost * abs(quantity)

    return Position(
        symbol=symbol,
        asset_type=asset_type,
        quantity=quantity,
        market_value=float(item.marketValue),
        cost_basis=cost_basis,
        unrealized_pnl=float(item.unrealizedPNL) if item.unrealizedPNL else 0.0,
        currency=contract.currency,
        expiration=expiration,
        strike=strike,
        option_type=option_type,
        underlying=underlying,
        delta=None,
        underlying_price=None,
    )


def _format_expiry(expiry: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD; pass through if already formatted."""
    clean = expiry.replace("-", "")
    if len(clean) == 8 and clean.isdigit():
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:8]}"
    return expiry

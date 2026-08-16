from __future__ import annotations

import logging
from datetime import UTC, datetime

from ib_insync import IB, Option, PortfolioItem, Stock

from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position

logger = logging.getLogger(__name__)

# TWS generic tick IDs used by the options screener.  Keep this mapping next
# to the transport call so field-code changes do not leak into report logic.
OPTION_MARKET_DATA_TICKS = {
    "historical_volatility": "104",
    "option_implied_volatility": "106",
    "real_time_historical_volatility": "411",
}

_GATEWAY_NOT_RUNNING = (
    "Error: IB Gateway is not running on {host}:{port}\n"
    "Ensure IB Gateway is open, API is enabled on port {port}, and WSL access is allowed."
)


class IBKRConnectionError(RuntimeError):
    pass


class IBKRClient:
    """Thin wrapper over ib_insync's TWS API.

    Supports both one-shot calls (connect/disconnect per call, the
    original behavior) and a reused connection across several calls via
    `connect()`/`disconnect()` or the context-manager form — callers that
    need many sequential requests (e.g. the options screener fetching IV
    for several contracts) should hold one connection open instead of
    reconnecting to Gateway per request.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7496,
        client_id: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._ib: IB | None = None

    def connect(self) -> None:
        if self._ib is not None and self._ib.isConnected():
            return
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
        self._ib = ib

    def disconnect(self) -> None:
        if self._ib is not None:
            self._ib.disconnect()
            self._ib = None

    def __enter__(self) -> "IBKRClient":
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.disconnect()

    def get_portfolio(self) -> Portfolio:
        owns_connection = self._ib is None
        if owns_connection:
            self.connect()
        ib = self._ib
        assert ib is not None
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
            if owns_connection:
                self.disconnect()

    def get_option_market_data(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        right: str,
        exchange: str = "SMART",
    ) -> dict[str, object]:
        """Return a read-only option market-data snapshot for one contract.

        `expiration` must be `YYYYMMDD` (ib_insync's
        `lastTradeDateOrContractMonth` format) — an ISO `YYYY-MM-DD` string
        fails contract qualification silently (empty result).

        The raw ticker fields are intentionally returned as a mapping so
        callers can apply their own validity rules without coupling this
        transport layer to a report or screener model. Only fields that
        actually exist on ib_insync's `Ticker`/`OptionComputation` are read
        here — IBKR's IV Percentile is not exposed over the TWS API at all
        (see `get_underlying_iv_history` for the real source of that data).
        """
        owns_connection = self._ib is None
        if owns_connection:
            self.connect()
        ib = self._ib
        assert ib is not None
        try:
            contract = Option(
                symbol,
                expiration,
                float(strike),
                right,
                exchange,
                currency="USD",
            )
            qualified = ib.qualifyContracts(contract)
            if not qualified:
                return {}
            ticker = ib.reqMktData(
                qualified[0],
                genericTickList=",".join(OPTION_MARKET_DATA_TICKS.values()),
                snapshot=True,
            )
            ib.sleep(1)
            option_greeks = ticker.modelGreeks or ticker.bidGreeks or ticker.askGreeks
            return {
                "implied_vol": getattr(option_greeks, "impliedVol", None),
                "historical_vol": getattr(ticker, "histVolatility", None),
            }
        finally:
            if owns_connection:
                self.disconnect()

    def get_underlying_iv_history(
        self,
        symbol: str,
        exchange: str = "SMART",
        duration: str = "1 Y",
    ) -> list[dict[str, object]]:
        """Return the underlying's daily option-implied-volatility series.

        IBKR computes IV Percentile server-side only through the separate
        Client Portal Web API, which this project does not integrate with.
        Over the TWS API (what `IBKRClient` uses), the same data is
        available as a historical series via
        `reqHistoricalData(whatToShow="OPTION_IMPLIED_VOLATILITY")` — one
        bar per trading day, `close` is the underlying's implied vol as a
        fraction (e.g. 0.2225 = 22.25%). Callers compute percentile rank
        themselves from this series (see
        `options_screener.compute_iv_percentiles`).
        """
        owns_connection = self._ib is None
        if owns_connection:
            self.connect()
        ib = self._ib
        assert ib is not None
        try:
            contract = Stock(symbol, exchange, "USD")
            qualified = ib.qualifyContracts(contract)
            if not qualified:
                return []
            bars = ib.reqHistoricalData(
                qualified[0],
                endDateTime="",
                durationStr=duration,
                barSizeSetting="1 day",
                whatToShow="OPTION_IMPLIED_VOLATILITY",
                useRTH=True,
            )
            return [
                {"date": bar.date, "iv": bar.close}
                for bar in bars
                if bar.close is not None
            ]
        finally:
            if owns_connection:
                self.disconnect()


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

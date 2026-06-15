from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import requests
import urllib3

from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position

logger = logging.getLogger(__name__)

_GATEWAY_NOT_RUNNING = (
    "Error: IBKR Client Portal is not running on {url}\n"
    "Start it with: /path/to/clientportal.gw/bin/run.sh root/conf.yaml"
)


class IBKRConnectionError(RuntimeError):
    pass


class IBKRClient:
    def __init__(self, gateway_url: str = "https://localhost:5000") -> None:
        self._base_url = gateway_url.rstrip("/")
        self._session = requests.Session()
        self._session.verify = False
        # Self-signed cert is expected for IBKR Client Portal localhost gateway
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.warning(
            "IBKR Client Portal uses a self-signed certificate — "
            "SSL verification disabled (localhost only)"
        )

    def get_portfolio(self) -> Portfolio:
        account_id = self._get_first_account()
        summary = self._get_account_summary(account_id)
        cash = self._get_cash_balances(account_id)
        positions = self._get_positions(account_id)
        return Portfolio(
            account_id=account_id,
            as_of=datetime.now(UTC).isoformat(),
            summary=summary,
            cash=cash,
            positions=positions,
        )

    def _get(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            raise IBKRConnectionError(
                _GATEWAY_NOT_RUNNING.format(url=self._base_url)
            ) from exc
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", "unknown")
            raise IBKRConnectionError(
                f"IBKR gateway HTTP error {status} for {url}"
            ) from exc

    def _get_first_account(self) -> str:
        data = self._get("/v1/api/portfolio/accounts")
        if not data:
            raise IBKRConnectionError("No accounts returned from IBKR gateway")
        account = data[0]
        return str(account.get("accountId") or account.get("id") or "")

    def _get_account_summary(self, account_id: str) -> AccountSummary:
        data = self._get(f"/v1/api/portfolio/{account_id}/summary")

        def _amount(key: str) -> float:
            entry = data.get(key, {})
            if isinstance(entry, dict):
                return float(entry.get("amount", 0.0))
            return float(entry or 0.0)

        nlv = _amount("netliquidation")
        initial_margin = _amount("initmarginreq")
        leverage = (initial_margin / nlv) if nlv > 0 else None

        return AccountSummary(
            net_liquidation=nlv,
            total_cash=_amount("totalcashvalue"),
            buying_power=_amount("buyingpower"),
            initial_margin=initial_margin,
            maintenance_margin=_amount("maintmarginreq"),
            excess_liquidity=_amount("excessliquidity"),
            leverage=leverage,
        )

    def _get_cash_balances(self, account_id: str) -> list[CashBalance]:
        data = self._get(f"/v1/api/portfolio/{account_id}/ledger")
        balances: list[CashBalance] = []
        for currency, entry in data.items():
            if not isinstance(entry, dict):
                continue
            balances.append(
                CashBalance(
                    currency=currency,
                    balance=float(entry.get("cashbalance", 0.0)),
                    settled_cash=float(entry.get("settledcash", 0.0)),
                )
            )
        return balances

    def _get_positions(self, account_id: str) -> list[Position]:
        data = self._get(f"/v1/api/portfolio/{account_id}/positions/0")
        positions: list[Position] = []
        for raw in data:
            try:
                positions.append(_parse_position(raw))
            except Exception as exc:
                logger.debug("Skipping unparseable position: %s — %s", raw, exc)
        return positions


def _parse_position(raw: dict[str, Any]) -> Position:
    asset_class = str(raw.get("assetClass") or raw.get("asset_class") or "STK").upper()

    ticker = str(raw.get("ticker") or "")
    contract_desc = str(raw.get("contractDesc") or "")
    symbol_raw = ticker if ticker else (contract_desc or "UNKNOWN")

    underlying: str | None = None
    if asset_class == "OPT":
        underlying = (
            ticker if ticker else (contract_desc.split()[0] if contract_desc else None)
        )
        symbol_display = contract_desc if contract_desc else symbol_raw
    else:
        symbol_display = symbol_raw

    expiry_raw = raw.get("expiry") or raw.get("expiration")
    expiration: str | None = None
    if expiry_raw and str(expiry_raw).strip():
        expiration = _format_expiry(str(expiry_raw).strip())

    put_or_call = raw.get("putOrCall") or raw.get("putorcall")
    option_type: str | None = None
    if put_or_call:
        option_type = "PUT" if str(put_or_call).upper() in ("P", "PUT") else "CALL"

    strike_raw = raw.get("strike")
    strike: float | None = float(strike_raw) if strike_raw is not None else None
    if strike == 0.0:
        strike = None

    delta_raw = raw.get("delta")
    delta: float | None = float(delta_raw) if delta_raw is not None else None

    und_price_raw = raw.get("undPrice") or raw.get("und_price")
    underlying_price: float | None = float(und_price_raw) if und_price_raw else None

    quantity = float(raw.get("position", 0.0))
    market_value = float(raw.get("mktValue", 0.0))
    avg_cost = float(raw.get("avgCost") or raw.get("avgPrice") or 0.0)
    cost_basis = avg_cost * abs(quantity)
    unrealized_pnl = float(raw.get("unrealizedPnl", 0.0))
    currency = str(raw.get("currency", "USD"))

    return Position(
        symbol=symbol_display,
        asset_type=asset_class,
        quantity=quantity,
        market_value=market_value,
        cost_basis=cost_basis,
        unrealized_pnl=unrealized_pnl,
        currency=currency,
        expiration=expiration,
        strike=strike,
        option_type=option_type,
        underlying=underlying,
        delta=delta,
        underlying_price=underlying_price,
    )


def _format_expiry(expiry: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD; pass through if already formatted."""
    expiry = expiry.replace("-", "")
    if len(expiry) == 8 and expiry.isdigit():
        return f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}"
    return expiry

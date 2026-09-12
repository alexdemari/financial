"""Incremental Binance Spot trade synchronization."""

import logging
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from crypto_trades.models import CryptoTrade

logger = logging.getLogger(__name__)


class BinanceTradeClient(Protocol):
    def get_my_trades(
        self, symbol: str, from_id: int | None = None
    ) -> list[dict[str, object]]: ...


def fetch_new_trades(
    client: BinanceTradeClient,
    symbols: list[str],
    known_execution_ids_by_symbol: dict[str, set[str]],
) -> list[CryptoTrade]:
    """Fetch and normalize executions not already present in canonical history."""
    trades: list[CryptoTrade] = []
    for symbol in symbols:
        known_execution_ids = known_execution_ids_by_symbol.get(symbol, set())
        prior_ids = [
            int(execution_id)
            for execution_id in known_execution_ids
            if execution_id.isdigit()
        ]
        from_id = max(prior_ids) + 1 if prior_ids else None
        try:
            executions = client.get_my_trades(symbol, from_id=from_id)
        except Exception:
            logger.exception("Skipping Binance trade sync for %s", symbol)
            continue
        for execution in executions:
            trade_id = str(execution.get("id", ""))
            canonical_id = f"api_{symbol}_{trade_id}"
            if not trade_id or trade_id in known_execution_ids:
                continue
            trades.append(_api_trade(execution, symbol, canonical_id))
    return trades


def build_known_execution_ids_by_symbol(
    existing_trades: list[CryptoTrade], symbols: list[str]
) -> dict[str, set[str]]:
    """Associate persisted API/export execution IDs with their exact Spot pair."""
    known_ids = {symbol: set() for symbol in symbols}
    for trade in existing_trades:
        if trade.source == "api":
            for symbol in symbols:
                api_prefix = f"api_{symbol}_"
                if trade.trade_id.startswith(api_prefix):
                    known_ids[symbol].add(trade.trade_id.removeprefix(api_prefix))
        elif trade.source == "export":
            for symbol in symbols:
                if symbol.removesuffix("USDT") == trade.asset:
                    known_ids[symbol].add(trade.trade_id)
    return known_ids


def _api_trade(execution: dict[str, object], symbol: str, trade_id: str) -> CryptoTrade:
    quantity = float(execution.get("qty", 0) or 0)
    price = float(execution.get("price", 0) or 0)
    timestamp = datetime.fromtimestamp(
        float(execution.get("time", 0)) / 1000, tz=timezone.utc
    ).astimezone(ZoneInfo("America/Sao_Paulo"))
    return CryptoTrade(
        trade_id=trade_id,
        date=timestamp.date().isoformat(),
        datetime=timestamp.isoformat(),
        trade_type="BUY" if execution.get("isBuyer") else "SELL",
        asset=symbol.removesuffix("USDT"),
        quantity=quantity,
        price_usdt=price,
        total_usdt=float(execution.get("quoteQty", quantity * price) or 0),
        fee_amount=float(execution.get("commission", 0) or 0),
        fee_currency=str(execution.get("commissionAsset", "")),
        fee_value_brl=0.0,
        value_brl_binance=0.0,
        source="api",
        order_type="API",
    )

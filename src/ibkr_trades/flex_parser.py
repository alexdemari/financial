from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from ibkr_trades.models import TradeRecord

_ASSET_TYPES = {"OPT", "STK", "ETF"}


def _parse_date(s: str) -> date:
    s = s.strip()
    # Flex dates are YYYY-MM-DD or YYYYMMDD
    if len(s) == 8 and "-" not in s:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    return date.fromisoformat(s[:10])


def _float_or_none(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _map_put_call(s: str | None) -> str | None:
    if not s:
        return None
    return "PUT" if s.upper() == "P" else "CALL"


def _format_expiry(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) == 8 and "-" not in s:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10]


def parse_flex_xml(path: Path) -> list[TradeRecord]:
    """Parse IBKR Flex Query XML export. Returns OPT/STK/ETF trades only."""
    tree = ET.parse(path)
    root = tree.getroot()
    records: list[TradeRecord] = []

    for trade in root.iter("Trade"):
        asset_cat = trade.get("assetCategory", "")
        if asset_cat not in _ASSET_TYPES:
            continue

        trade_id = trade.get("tradeID", "") or trade.get("execID", "")
        date_str = trade.get("tradeDate", "")
        if not date_str or not trade_id:
            continue

        records.append(
            TradeRecord(
                trade_id=trade_id,
                date=_parse_date(date_str),
                datetime=trade.get("dateTime", "").replace(";", "T"),
                symbol=trade.get("symbol", ""),
                underlying=trade.get("underlyingSymbol", "") or trade.get("symbol", ""),
                asset_type=asset_cat,
                option_type=_map_put_call(trade.get("putCall")),
                strike=_float_or_none(trade.get("strike")),
                expiration=_format_expiry(trade.get("expiry")),
                quantity=float(trade.get("quantity", 0)),
                price=float(trade.get("tradePrice", 0)),
                proceeds=float(trade.get("proceeds", 0)),
                commission=float(trade.get("ibCommission", 0)),
                pnl_realized=_float_or_none(trade.get("fifoPnlRealized")),
                currency=trade.get("currency", "USD"),
                open_close=trade.get("openCloseIndicator", ""),
                source="flex",
            )
        )

    return records

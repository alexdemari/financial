from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from web.readers.history_jsonl import read_account_snapshot
from web.readers.ibkr_csv import read_positions, serialize_positions
from web.readers.tracker_csv import read_open_legs

router = APIRouter(prefix="/api")


@router.get("/account")
def get_account() -> dict:
    snapshot = read_account_snapshot()
    if snapshot is None:
        return {"error": "no_data", "hint": "Run: just ibkr-positions"}
    return asdict(snapshot)


@router.get("/positions")
def get_positions() -> list[dict]:
    return serialize_positions(read_positions())


@router.get("/options")
def get_options() -> dict:
    return read_open_legs()


@router.get("/risk")
def get_risk() -> dict:
    positions = read_positions()
    alerts = [
        {
            "type": "concentration",
            "symbol": position.symbol,
            "message": f"{position.symbol} is {position.weight:.1%} of NLV",
        }
        for position in positions
        if position.asset_type in {"STK", "ETF"} and position.weight >= 0.25
    ]
    snapshot = read_account_snapshot()
    required_cash = sum(
        abs(position.quantity) * (position.strike or 0.0) * 100
        for position in positions
        if position.asset_type == "OPT"
        and position.option_type == "PUT"
        and position.quantity < 0
    )
    shortfall = max(required_cash - snapshot.cash, 0.0) if snapshot else None
    if shortfall:
        alerts.append(
            {
                "type": "cash_shortfall",
                "message": f"Cash shortfall: ${shortfall:,.2f}",
            }
        )
    return {
        "alerts": alerts,
        "shortfall": shortfall,
        "last_updated": snapshot.last_updated if snapshot else None,
    }

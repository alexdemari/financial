from fastapi import APIRouter

from web.readers.trades_reader import (
    read_all_trades,
    read_monthly_summary,
    read_trade_sources,
)

router = APIRouter(prefix="/api")


@router.get("/trades")
def get_trades() -> dict:
    trades = read_all_trades()
    return {
        "trades": trades,
        "monthly_summary": read_monthly_summary(trades),
        "sources": read_trade_sources(),
    }

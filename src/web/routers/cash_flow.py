from fastapi import APIRouter

from web.readers.cash_flow_reader import (
    read_cash_flow_sources,
    read_cash_transactions,
    read_cumulative_contributed,
    read_nav_reconciliation,
)

router = APIRouter(prefix="/api")


@router.get("/cash-flow")
def get_cash_flow() -> dict:
    return {
        "transactions": read_cash_transactions(),
        "reconciliation": read_nav_reconciliation(),
        "cumulative_contributed": read_cumulative_contributed(),
        "source": read_cash_flow_sources(),
    }

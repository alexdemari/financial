from __future__ import annotations

from datetime import date, datetime, timedelta

from ib_insync import IB, ExecutionFilter

from ibkr_trades.models import TradeRecord

_OPT_TYPES = {"OPT", "STK", "ETF"}


def _format_expiry(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) == 8 and "-" not in s:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10]


def _parse_exec_time(t: datetime | str) -> tuple[date, str]:
    """Return (trade_date, iso_datetime_str) from ib_insync Execution.time.

    ib_insync delivers Execution.time as a datetime object.
    Guard against a string fallback from older versions.
    """
    if isinstance(t, datetime):
        return t.date(), t.isoformat()
    # Fallback: ib_insync string format is "YYYYMMDD  HH:MM:SS"
    s = str(t).strip().replace("  ", "T").replace(" ", "T")
    trade_date = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return trade_date, s


def fetch_recent_trades(
    ib: IB,
    account_id: str,
    since: date | None = None,
) -> list[TradeRecord]:
    """Fetch executions from IB Gateway via ib_insync since `since` date."""
    since = since or (date.today() - timedelta(days=7))
    fills = ib.reqExecutions(
        ExecutionFilter(
            acctCode=account_id,
            time=since.strftime("%Y%m%d %H:%M:%S"),
        )
    )

    records: list[TradeRecord] = []
    for fill in fills:
        exec_ = fill.execution
        contract = fill.contract
        if contract.secType not in _OPT_TYPES:
            continue

        trade_date, trade_datetime = _parse_exec_time(exec_.time)

        is_buy = exec_.side.upper() == "BOT"
        quantity = exec_.shares * (1 if is_buy else -1)
        multiplier = 100 if contract.secType == "OPT" else 1
        proceeds = exec_.shares * exec_.price * multiplier * (1 if is_buy else -1)

        # ib_insync exposes openClose on Execution; absent in older API responses → default ""
        open_close = getattr(exec_, "openClose", "") or ""

        records.append(
            TradeRecord(
                trade_id=exec_.execId,
                date=trade_date,
                datetime=trade_datetime,
                symbol=contract.localSymbol,
                underlying=contract.symbol,
                asset_type=contract.secType,
                option_type=contract.right if contract.secType == "OPT" else None,
                strike=contract.strike if contract.secType == "OPT" else None,
                expiration=_format_expiry(contract.lastTradeDateOrContractMonth),
                quantity=quantity,
                price=exec_.price,
                proceeds=proceeds,
                commission=0.0,
                pnl_realized=None,
                currency=contract.currency,
                open_close=open_close,
                source="api",
            )
        )

    return records

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from web.readers.common import PROJECT_ROOT

CASH_TRANSACTIONS = PROJECT_ROOT / "data/ibkr/cash_transactions.csv"
NAV_CHANGES = PROJECT_ROOT / "data/ibkr/nav_changes.csv"
RECONCILIATION_TOLERANCE_USD = 1.0


@dataclass(frozen=True)
class CashTransactionRow:
    date: str
    type: str
    amount: float
    currency: str
    description: str


@dataclass(frozen=True)
class NavReconciliation:
    from_date: str
    to_date: str
    starting_value: float
    ending_value: float
    deposits_withdrawals: float
    net_trades: float
    reconciles: bool
    diff: float


def read_cash_transactions() -> list[dict]:
    """Read IBKR cash transactions, newest first, without writing to disk."""
    frame = _read_csv(CASH_TRANSACTIONS)
    required = {"date", "type", "amount", "currency", "description"}
    if frame.empty or not required.issubset(frame.columns):
        return []

    rows = []
    for _, row in frame.iterrows():
        amount = _to_float(row["amount"])
        if amount is None:
            continue
        rows.append(
            asdict(
                CashTransactionRow(
                    date=_date_text(row["date"]),
                    type=str(row["type"]),
                    amount=amount,
                    currency=str(row["currency"]),
                    description=str(row["description"]),
                )
            )
        )
    return sorted(rows, key=lambda row: row["date"], reverse=True)


def read_nav_reconciliation() -> list[dict]:
    """Calculate period-by-period NAV reconciliation for the dashboard."""
    frame = _read_csv(NAV_CHANGES)
    required = {
        "from_date",
        "to_date",
        "starting_value",
        "ending_value",
        "deposits_withdrawals",
        "net_trades",
    }
    if frame.empty or not required.issubset(frame.columns):
        return []

    rows = []
    for _, row in frame.iterrows():
        starting_value = float(row["starting_value"])
        ending_value = float(row["ending_value"])
        deposits_withdrawals = float(row["deposits_withdrawals"])
        net_trades = float(row["net_trades"])
        diff = starting_value + deposits_withdrawals + net_trades - ending_value
        rows.append(
            asdict(
                NavReconciliation(
                    from_date=_date_text(row["from_date"]),
                    to_date=_date_text(row["to_date"]),
                    starting_value=starting_value,
                    ending_value=ending_value,
                    deposits_withdrawals=deposits_withdrawals,
                    net_trades=net_trades,
                    reconciles=abs(diff) <= RECONCILIATION_TOLERANCE_USD,
                    diff=round(diff, 2),
                )
            )
        )
    return rows


def read_cumulative_contributed() -> list[dict]:
    """Return the running net contribution per currency, ordered chronologically."""
    frame = _read_csv(CASH_TRANSACTIONS)
    required = {"date", "type", "amount", "currency"}
    if frame.empty or not required.issubset(frame.columns):
        return []

    deposits = frame[frame["type"] == "Deposits/Withdrawals"].copy()
    if deposits.empty:
        return []
    deposits["date"] = deposits["date"].map(_date_text)
    deposits["amount"] = deposits["amount"].map(_to_float)
    deposits = deposits.dropna(subset=["amount"]).sort_values("date")
    deposits["contributed"] = deposits.groupby("currency")["amount"].cumsum()
    return deposits[["date", "currency", "contributed"]].to_dict(orient="records")


def read_cash_flow_sources() -> dict[str, str | None]:
    """Return relative source paths, or ``None`` when a source is unavailable."""
    return {
        name: (str(path.relative_to(PROJECT_ROOT)) if path.exists() else None)
        for name, path in (
            ("cash_transactions", CASH_TRANSACTIONS),
            ("nav_changes", NAV_CHANGES),
        )
    }


def _read_csv(path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def _date_text(value: object) -> str:
    return pd.to_datetime(value).date().isoformat()


def _to_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result

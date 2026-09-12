"""Parse Binance Transaction History CSV exports."""

import csv
from datetime import datetime
from pathlib import Path

from crypto_trades.classifier import STABLE_COINS, classify, get_asset
from crypto_trades.models import CryptoTrade, EarnRecord


def parse_export_csv(path: Path) -> tuple[list[CryptoTrade], list[EarnRecord]]:
    """Parse an export into canonical trades and separate Simple Earn records."""
    with path.open(encoding="utf-8-sig", newline="") as export_file:
        rows = list(csv.DictReader(export_file))
    trades: list[CryptoTrade] = []
    earnings: list[EarnRecord] = []
    for row in rows:
        operation = classify(row)
        if operation == "EARN":
            earnings.append(_earn_record(row))
        elif operation in {
            "BUY",
            "SELL",
            "SWAP",
            "STABLE_SWAP",
            "DEPOSIT_FIAT",
            "SEND",
            "RECEIVE_EXTERNAL",
        }:
            trades.extend(_trade_records(row, operation))
    return trades, earnings


def _trade_records(row: dict[str, str], operation: str) -> list[CryptoTrade]:
    if operation == "SWAP":
        return [
            _trade_record(row, "SWAP_SELL", f"{row['id']}_A"),
            _trade_record(row, "SWAP_BUY", f"{row['id']}_B"),
        ]
    return [_trade_record(row, operation, row["id"])]


def _trade_record(row: dict[str, str], operation: str, trade_id: str) -> CryptoTrade:
    quantity = _number(
        row.get("received_amount")
        if operation
        in {"BUY", "SWAP_BUY", "STABLE_SWAP", "DEPOSIT_FIAT", "RECEIVE_EXTERNAL"}
        else row.get("sent_amount")
    )
    total_usdt = _stable_amount(row, operation)
    return CryptoTrade(
        trade_id=trade_id,
        date=_date(row),
        datetime=_datetime(row),
        trade_type=operation,
        asset=get_asset(row, operation),
        quantity=quantity,
        price_usdt=total_usdt / quantity if quantity else 0.0,
        total_usdt=total_usdt,
        fee_amount=_number(row.get("fee_amount")),
        fee_currency=row.get("fee_currency", "").upper(),
        fee_value_brl=_number(row.get("fee_value_BRL")),
        value_brl_binance=_number(
            row.get("received_value_BRL")
            if operation
            in {"BUY", "SWAP_BUY", "STABLE_SWAP", "DEPOSIT_FIAT", "RECEIVE_EXTERNAL"}
            else row.get("sent_value_BRL")
        ),
        order_type=row.get("order_type", ""),
    )


def _earn_record(row: dict[str, str]) -> EarnRecord:
    return EarnRecord(
        trade_id=row["id"],
        date=_date(row),
        asset=row.get("received_currency", "").upper(),
        quantity=_number(row.get("received_amount")),
        value_brl_binance=_number(row.get("received_value_BRL")),
        earn_type=row.get("market_model_type", ""),
    )


def _stable_amount(row: dict[str, str], operation: str) -> float:
    stable_currency = (
        row.get("received_currency")
        if operation == "SELL"
        else row.get("sent_currency")
    )
    amount = (
        row.get("received_amount") if operation == "SELL" else row.get("sent_amount")
    )
    return _number(amount) if (stable_currency or "").upper() in STABLE_COINS else 0.0


def _date(row: dict[str, str]) -> str:
    return _parse_datetime(row).date().isoformat()


def _datetime(row: dict[str, str]) -> str:
    return _parse_datetime(row).isoformat()


def _parse_datetime(row: dict[str, str]) -> datetime:
    value = next(
        (value for key, value in row.items() if key.startswith("datetime")), ""
    )
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def _number(value: object) -> float:
    try:
        return float(str(value or "").replace(",", ""))
    except ValueError:
        return 0.0

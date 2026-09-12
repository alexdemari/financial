"""CSV persistence with stable idempotent trade identifiers."""

import csv
from pathlib import Path
from typing import Protocol

from crypto_trades.models import CryptoTrade, EarnRecord


class CsvRecord(Protocol):
    trade_id: str

    def to_dict(self) -> dict[str, object]: ...


TRADE_FIELDS = list(CryptoTrade.__dataclass_fields__)
EARN_FIELDS = list(EarnRecord.__dataclass_fields__)


def append_deduplicated(
    path: Path, records: list[CsvRecord], fieldnames: list[str]
) -> int:
    """Append records whose trade IDs are absent from *path*, returning count added."""
    existing_ids = _existing_ids(path)
    additions = [record for record in records if record.trade_id not in existing_ids]
    if not additions:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(record.to_dict() for record in additions)
    return len(additions)


def load_trades(path: Path) -> list[CryptoTrade]:
    """Load canonical trades, returning an empty list if no history exists."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as input_file:
        return [_trade_from_row(row) for row in csv.DictReader(input_file)]


def _existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as input_file:
        return {row["trade_id"] for row in csv.DictReader(input_file)}


def _trade_from_row(row: dict[str, str]) -> CryptoTrade:
    values = dict(row)
    for field in (
        "quantity",
        "price_usdt",
        "total_usdt",
        "fee_amount",
        "fee_value_brl",
        "value_brl_binance",
        "value_brl_ptax",
    ):
        values[field] = float(values[field] or 0)
    values["ptax_bcb"] = float(values["ptax_bcb"]) if values.get("ptax_bcb") else None
    return CryptoTrade(**values)

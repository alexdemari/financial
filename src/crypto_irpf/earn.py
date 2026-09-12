"""Simple Earn income loading and annual summaries."""

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from crypto_trades.models import EarnRecord


@dataclass
class EarnSummary:
    total_brl: float
    by_type_brl: dict[str, float]


def load_earn_records(path: Path, year: int) -> list[EarnRecord]:
    """Load earnings for one calendar year from canonical CSV storage."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = csv.DictReader(input_file)
        return [_earn_record(row) for row in rows if row["date"].startswith(str(year))]


def summarize_earn(records: list[EarnRecord]) -> EarnSummary:
    """Group annual PTAX-valued Simple Earn income by program type."""
    amounts: dict[str, float] = defaultdict(float)
    for record in records:
        amounts[record.earn_type or "UNSPECIFIED"] += record.value_brl_ptax
    by_type_brl = dict(sorted(amounts.items()))
    return EarnSummary(total_brl=sum(by_type_brl.values()), by_type_brl=by_type_brl)


def _earn_record(row: dict[str, str]) -> EarnRecord:
    return EarnRecord(
        trade_id=row["trade_id"],
        date=row["date"],
        asset=row["asset"],
        quantity=float(row["quantity"] or 0),
        value_brl_binance=float(row["value_brl_binance"] or 0),
        ptax_bcb=float(row["ptax_bcb"]) if row.get("ptax_bcb") else None,
        value_brl_ptax=float(row["value_brl_ptax"] or 0),
        earn_type=row.get("earn_type", ""),
        source=row.get("source", "export"),
    )

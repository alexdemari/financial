from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from web.readers.common import PROJECT_ROOT

REPORTS_DIR = PROJECT_ROOT / "reports/output"


@dataclass(frozen=True)
class Position:
    symbol: str
    asset_type: str
    quantity: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float
    return_pct: float
    weight: float
    option_type: str | None
    strike: float | None
    expiration: str | None
    dte: int | None
    risk_status: str | None


def latest_ibkr_csv() -> Path | None:
    files = sorted(REPORTS_DIR.glob("ibkr_positions_*.csv"))
    return files[-1] if files else None


def option_risk_status(dte: int) -> str:
    if dte <= 7:
        return "EXIT"
    if dte <= 14:
        return "WATCH"
    return "HOLD"


def read_positions(today: date | None = None) -> list[Position]:
    path = latest_ibkr_csv()
    if path is None:
        return []
    rows = _read_rows(path)
    reference_date = today or date.today()
    positions: list[Position] = []
    for row in rows:
        symbol = _text(row.get("symbol"))
        asset_type = _text(row.get("type"))
        if symbol is None or asset_type is None:
            continue
        market_value = _float(row.get("market_value"))
        cost_basis = _float(row.get("cost_basis"))
        expiration = _text(row.get("expiration"))
        dte = _days_to_expiration(expiration, reference_date)
        positions.append(
            Position(
                symbol=symbol,
                asset_type=asset_type,
                quantity=_float(row.get("qty")),
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_pnl=_float(row.get("unrealized_pnl")),
                return_pct=(
                    _float(row.get("unrealized_pnl")) / abs(cost_basis)
                    if cost_basis
                    else 0.0
                ),
                weight=_float(row.get("weight")),
                option_type=_text(row.get("option_type")),
                strike=_optional_float(row.get("strike")),
                expiration=expiration,
                dte=dte,
                risk_status=option_risk_status(dte) if dte is not None else None,
            )
        )
    return positions


def serialize_positions(positions: list[Position]) -> list[dict]:
    return [asdict(position) for position in positions]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def _optional_float(value: str | None) -> float | None:
    return None if not value else _float(value)


def _text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _days_to_expiration(expiration: str | None, reference_date: date) -> int | None:
    if expiration is None:
        return None
    try:
        return (date.fromisoformat(expiration) - reference_date).days
    except ValueError:
        return None

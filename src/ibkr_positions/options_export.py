from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path

from ibkr_positions.models import Portfolio, Position
from market_scanner.options_tracker_schema import (
    OPTIONS_TRACKER_COLUMNS,
    format_contract_quantity,
    format_european_float,
)

OPTIONS_TRACKER_LIVE_FILENAME = "options_tracker_live.csv"
OPTIONS_TRACKER_LIVE_COLUMNS = list(OPTIONS_TRACKER_COLUMNS)

logger = logging.getLogger(__name__)


def write_options_tracker_live_csv(
    portfolio: Portfolio,
    output_dir: str | Path = "reports/output",
    as_of: date | None = None,
) -> Path:
    """Write live IBKR option positions in exit_monitor-compatible CSV format."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / OPTIONS_TRACKER_LIVE_FILENAME

    today = as_of or date.today()
    option_rows = []
    for position in portfolio.positions:
        if position.asset_type != "OPT" or position.quantity == 0:
            continue
        row = _position_to_options_tracker_row(position, today)
        if row is not None:
            option_rows.append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=OPTIONS_TRACKER_LIVE_COLUMNS,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(option_rows)

    return csv_path


def _position_to_options_tracker_row(
    position: Position, as_of: date
) -> dict[str, str] | None:
    if not position.underlying:
        logger.warning("Skipping option %s: missing underlying symbol", position.symbol)
        return None

    expiration_date = _parse_expiration(position.expiration)
    if expiration_date is None:
        logger.warning(
            "Skipping option %s: invalid expiration %r",
            position.symbol,
            position.expiration,
        )
        return None

    return {
        "entry_date": "",
        "platform": "IBKR",
        "currency": position.currency,
        "symbol": position.underlying,
        "underlying": position.underlying,
        "option_type": (position.option_type or "").upper(),
        "open_direction": _open_direction(position.quantity),
        "expiration": expiration_date.isoformat(),
        "strike": format_european_float(position.strike),
        "premium_received": format_european_float(position.cost_basis),
        "quantity": format_contract_quantity(position.quantity),
        "current_value": format_european_float(position.market_value),
        "unrealized_pnl": format_european_float(position.unrealized_pnl),
        "delta": format_european_float(position.delta),
        "iv": "",
        "dte": str((expiration_date - as_of).days),
        "collateral": "",
        "close_action": "",
        "close_date": "",
        "close_quantity": "",
        "close_value": "",
        "close_costs": "",
        "result": "",
        "size": "",
        "close_description": "",
        "signal_source": "ibkr_live",
    }


def _open_direction(quantity: float) -> str:
    if quantity == 0:
        raise ValueError("Zero-quantity positions have no open direction")
    return "V" if quantity < 0 else "C"


def _parse_expiration(value: str | None) -> date | None:
    if not value:
        return None
    normalized_value = value.strip()
    if len(normalized_value) == 8 and normalized_value.isdigit():
        normalized_value = (
            f"{normalized_value[:4]}-{normalized_value[4:6]}-{normalized_value[6:]}"
        )
    try:
        return date.fromisoformat(normalized_value)
    except ValueError:
        try:
            return datetime.fromisoformat(normalized_value).date()
        except ValueError:
            return None

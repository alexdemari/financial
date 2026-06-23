from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from ibkr_positions.models import Portfolio, Position

OPTIONS_TRACKER_LIVE_FILENAME = "options_tracker_live.csv"

OPTIONS_TRACKER_LIVE_COLUMNS = [
    "entry_date",
    "platform",
    "currency",
    "symbol",
    "underlying",
    "option_type",
    "open_direction",
    "expiration",
    "strike",
    "premium_received",
    "quantity",
    "current_value",
    "unrealized_pnl",
    "delta",
    "iv",
    "dte",
    "collateral",
    "close_action",
    "close_date",
    "close_quantity",
    "close_value",
    "close_costs",
    "result",
    "size",
    "close_description",
    "signal_source",
]


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
    option_positions = [
        position for position in portfolio.positions if position.asset_type == "OPT"
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=OPTIONS_TRACKER_LIVE_COLUMNS,
            delimiter=";",
        )
        writer.writeheader()
        for position in option_positions:
            writer.writerow(_position_to_options_tracker_row(position, today))

    return csv_path


def _position_to_options_tracker_row(position: Position, as_of: date) -> dict[str, str]:
    if position.expiration is None:
        expiration_date = None
        dte = ""
    else:
        expiration_date = date.fromisoformat(position.expiration)
        dte = str((expiration_date - as_of).days)

    return {
        "entry_date": as_of.isoformat(),
        "platform": "IBKR",
        "currency": position.currency,
        "symbol": position.underlying or position.symbol,
        "underlying": position.underlying or position.symbol,
        "option_type": (position.option_type or "").upper(),
        "open_direction": _open_direction(position.quantity),
        "expiration": expiration_date.isoformat() if expiration_date else "",
        "strike": _format_decimal(position.strike),
        "premium_received": _format_decimal(position.cost_basis),
        "quantity": _format_quantity(position.quantity),
        "current_value": _format_decimal(position.market_value),
        "unrealized_pnl": _format_decimal(position.unrealized_pnl),
        "delta": _format_decimal(position.delta),
        "iv": "",
        "dte": dte,
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
    return "V" if quantity < 0 else "C"


def _format_decimal(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",")


def _format_quantity(quantity: float) -> str:
    if quantity.is_integer():
        return str(int(quantity))
    return str(quantity).replace(".", ",")

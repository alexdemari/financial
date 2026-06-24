from __future__ import annotations

OPTIONS_TRACKER_COLUMNS = (
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
)


def format_european_float(value: float | None, decimal_places: int = 2) -> str:
    """Format a numeric tracker value using comma decimal separators."""
    if value is None:
        return ""
    return f"{value:.{decimal_places}f}".replace(".", ",")


def parse_european_float(value: str) -> float | None:
    """Parse a tracker number using optional dot thousands separators."""
    normalized_value = value.strip().replace(".", "").replace(",", ".")
    if not normalized_value:
        return None
    try:
        return float(normalized_value)
    except ValueError:
        return None


def format_contract_quantity(quantity: float) -> str:
    """Preserve integer and fractional contract quantities for round trips."""
    if quantity.is_integer():
        return str(int(quantity))
    return str(quantity).replace(".", ",")

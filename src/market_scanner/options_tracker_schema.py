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
    """Parse a tracker number in European (comma decimal) or US (period decimal) format."""
    s = value.strip()
    if not s:
        return None
    has_dot = "." in s
    has_comma = "," in s
    try:
        if has_dot and has_comma:
            if s.rfind(".") > s.rfind(","):
                return float(s.replace(",", ""))  # US thousands: 1,234.56
            else:
                return float(
                    s.replace(".", "").replace(",", ".")
                )  # EU thousands: 1.234,56
        elif has_comma:
            return float(s.replace(",", "."))  # EU decimal: 1,45
        else:
            return float(s)  # US decimal or integer: 2.86, 140
    except ValueError:
        return None


def format_contract_quantity(quantity: float) -> str:
    """Preserve integer and fractional contract quantities for round trips."""
    if quantity.is_integer():
        return str(int(quantity))
    return str(quantity).replace(".", ",")

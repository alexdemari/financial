from __future__ import annotations

import math
from typing import Any

_NULL_TOKENS = {"", "nan", "none", "<na>"}


def normalize_option_type(value: Any) -> str | None:
    """Canonical C/P -> CALL/PUT mapping shared by every trade ingestion path.

    Returns None for missing/blank/NaN input. Unknown non-empty values are
    upper-cased and passed through unchanged.
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    value_str = str(value).strip()
    if value_str.lower() in _NULL_TOKENS:
        return None
    value_str = value_str.upper()
    if value_str == "C":
        return "CALL"
    if value_str == "P":
        return "PUT"
    return value_str

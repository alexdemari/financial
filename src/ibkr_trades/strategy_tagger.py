from __future__ import annotations


def _is_set(value: object) -> bool:
    """True if value is a non-empty, non-NaN value. NaN fails value == value."""
    if value is None:
        return False
    try:
        return bool(value) and value == value
    except (TypeError, ValueError):
        return False


def infer_strategy(row: dict) -> str | None:
    """Infer option strategy from trade record fields. Ambiguous cases return 'other'."""
    if row.get("asset_type") != "OPT":
        return None
    if _is_set(row.get("roll_id")):
        return "roll"

    qty = row.get("quantity", 0)
    otype = row.get("option_type")
    oc = str(row.get("open_close", ""))

    if "O" not in oc:
        return None  # closing trade — no strategy to infer

    if qty < 0 and otype == "CALL":
        return "covered_call"
    if qty < 0 and otype == "PUT":
        return "csp"
    if qty > 0 and otype == "CALL":
        return "long_call"
    if qty > 0 and otype == "PUT":
        return "long_put"

    return "other"


def tag_strategies(df: "pd.DataFrame") -> "pd.DataFrame":  # noqa: F821
    """Apply infer_strategy to all rows, writing to 'strategy' column."""

    df = df.copy()
    df["strategy"] = df.apply(lambda r: infer_strategy(r.to_dict()), axis=1)
    return df

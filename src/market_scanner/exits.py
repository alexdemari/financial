from typing import Literal


TradeSide = Literal["bullish", "bearish"]


def exit_on_alignment_break(row: dict, side: TradeSide) -> bool:
    expected_alignment = "bullish_aligned" if side == "bullish" else "bearish_aligned"
    return row.get("adjusted_alignment") != expected_alignment


def exit_on_bucket_downgrade(row: dict) -> bool:
    return row.get("action_bucket") in {"watchlist", "avoid", "needs_review"}


def exit_on_late_state(row: dict) -> bool:
    return row.get("market_state") in {"extended", "exhaustion"}


def exit_on_opposite_signal(row: dict, side: TradeSide) -> bool:
    opposite_alignment = "bearish_aligned" if side == "bullish" else "bullish_aligned"
    return row.get("adjusted_alignment") == opposite_alignment


def exit_after_n_bars(bars_held: int, limit: int) -> bool:
    return bars_held >= limit

from types import SimpleNamespace

import pandas as pd

from market_scanner.ranking import signal_to_label


def optional_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def lux_context(signal) -> str:
    if (
        signal.confirmation_signal == signal.combined_signal
        and signal.combined_signal != 0
    ):
        return (
            "trend_confirmation_buy"
            if signal.options_hint == "CALL"
            else "trend_confirmation_sell"
        )
    if (
        signal.contrarian_signal == signal.combined_signal
        and signal.combined_signal != 0
    ):
        return (
            "contrarian_reversal_buy"
            if signal.options_hint == "CALL"
            else "contrarian_reversal_sell"
        )
    return "no_trade"


def smc_context(signal) -> str:
    if signal.long_signal:
        return "bullish_confluence"
    if signal.short_signal:
        return "bearish_confluence"
    if signal.swing_low_marker and signal.in_discount:
        return "short_term_bullish_reversal"
    if signal.swing_high_marker and signal.in_premium:
        return "short_term_bearish_reversal"
    if signal.in_discount and signal.bullish_rejection:
        return "discount_watch"
    if signal.in_premium and signal.bearish_rejection:
        return "premium_watch"
    if signal.swing_low_marker:
        return "swing_low_watch"
    if signal.swing_high_marker:
        return "swing_high_watch"
    return "no_trade"


def lux_signal_from_history(symbol: str, row: pd.Series):
    return SimpleNamespace(
        symbol=symbol,
        date=pd.Timestamp(row["date"]),
        close_price=float(row["close"]),
        trend=str(row["trend"]),
        strength=str(row["strength"]),
        options_hint=str(row["options_hint"]),
        adx=optional_float(row.get("adx")),
        confirmation_signal=int(row.get("confirmation_signal", 0)),
        contrarian_signal=int(row.get("contrarian_signal", 0)),
        combined_signal=int(row["combined_signal"]),
    )


def smc_signal_from_history(symbol: str, row: pd.Series):
    return SimpleNamespace(
        symbol=symbol,
        date=pd.Timestamp(row["date"]),
        close_price=float(row["close"]),
        combined_signal=int(row["combined_signal"]),
        bias=str(row.get("signal_bias", "NEUTRAL")),
        range_position_pct=optional_float(row.get("range_position_pct")),
        rsi=optional_float(row.get("rsi")),
        options_hint=str(row.get("options_hint", "NO_TRADE")),
        swing_high_marker=bool(row.get("swing_high_marker", False)),
        swing_low_marker=bool(row.get("swing_low_marker", False)),
        in_premium=bool(row.get("in_premium", False)),
        in_discount=bool(row.get("in_discount", False)),
        bullish_rejection=bool(row.get("bullish_rejection", False)),
        bearish_rejection=bool(row.get("bearish_rejection", False)),
        long_signal=bool(row.get("long_signal", False)),
        short_signal=bool(row.get("short_signal", False)),
    )


def latest_model_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    if historical.empty:
        return empty_event()

    event_rows = historical[event_mask(historical)]
    if event_rows.empty:
        return empty_event()

    return event_from_row(event_rows.iloc[-1], historical)


def active_lux_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    priority_contexts = (
        ("trend_confirmation_buy", "trend_confirmation_sell"),
        ("contrarian_reversal_buy", "contrarian_reversal_sell"),
    )
    return latest_event_by_priority(historical, priority_contexts)


def active_smc_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    priority_contexts = (
        ("short_term_bullish_reversal", "short_term_bearish_reversal"),
        ("bullish_confluence", "bearish_confluence"),
    )
    return latest_event_by_priority(historical, priority_contexts)


def rank_inputs(
    ranking_mode: str,
    current_options_hint: str,
    current_signal: str,
    latest_event: dict[str, str | int | None],
) -> tuple[str, str]:
    if ranking_mode == "recent-event":
        return (
            str(latest_event["options_hint"] or "NO_TRADE"),
            str(latest_event["signal"] or "HOLD"),
        )
    return current_options_hint, current_signal


def event_mask(historical: pd.DataFrame) -> pd.Series:
    if "options_hint" in historical.columns:
        return historical["options_hint"].fillna("NO_TRADE") != "NO_TRADE"
    return historical["combined_signal"] != 0


def empty_event() -> dict[str, str | int | None]:
    return {
        "signal": None,
        "options_hint": None,
        "context": None,
        "date": None,
        "days_since": None,
    }


def latest_event_by_priority(
    historical: pd.DataFrame,
    priority_contexts: tuple[tuple[str, str], ...],
) -> dict[str, str | int | None]:
    if historical.empty or "signal_context" not in historical.columns:
        return empty_event()

    priority_rank: dict[str, int] = {}
    for rank, (bullish_context, bearish_context) in enumerate(priority_contexts):
        priority_rank[bullish_context] = rank
        priority_rank[bearish_context] = rank

    matching = historical[
        historical["signal_context"].isin(priority_rank.keys())
    ].copy()
    if matching.empty:
        return empty_event()

    matching["_event_date"] = pd.to_datetime(matching["date"])
    matching["_priority_rank"] = matching["signal_context"].map(priority_rank)
    matching = matching.sort_values(
        ["_event_date", "_priority_rank"],
        ascending=[False, True],
    )
    return event_from_row(matching.iloc[0], historical)


def event_from_row(
    row: pd.Series, historical: pd.DataFrame
) -> dict[str, str | int | None]:
    last_date = pd.Timestamp(row["date"])
    final_date = pd.Timestamp(historical.iloc[-1]["date"])
    return {
        "signal": signal_to_label(row["combined_signal"]),
        "options_hint": str(row.get("options_hint", "NO_TRADE")),
        "context": str(row.get("signal_context", "no_trade")),
        "date": last_date.isoformat(),
        "days_since": int((final_date.normalize() - last_date.normalize()).days),
    }

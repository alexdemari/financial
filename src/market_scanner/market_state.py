from collections.abc import Mapping
from typing import Any


EARLY_TREND = "early_trend"
PULLBACK = "pullback"
EXTENDED = "extended"
EXHAUSTION = "exhaustion"
RANGE = "range"
UNKNOWN = "unknown"

MARKET_STATES = {
    EARLY_TREND,
    PULLBACK,
    EXTENDED,
    EXHAUSTION,
    RANGE,
    UNKNOWN,
}

BULLISH_WATCHLIST = "bullish_watchlist"
BEARISH_WATCHLIST = "bearish_watchlist"
RANGE_WATCHLIST = "range_watchlist"

CANDIDATE = "candidate"
WATCHLIST = "watchlist"
AVOID = "avoid"
NEEDS_REVIEW = "needs_review"


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _consistency_allows_candidate(value: Any) -> bool:
    consistency_score = _to_int(value)
    return consistency_score is not None and consistency_score >= 1


def classify_market_state(row: Mapping[str, Any]) -> str:
    lux_trend = str(row.get("lux_trend") or "")
    lux_strength = str(row.get("lux_strength") or "")
    lux_last_event = str(row.get("lux_last_event") or "")
    smc_bias = str(row.get("smc_bias") or "")

    range_position_pct = _to_float(row.get("smc_range_position_pct"))
    smc_rsi = _to_float(row.get("smc_rsi"))
    lux_days_since_last_event = _to_int(row.get("lux_days_since_last_event"))

    if range_position_pct is None or smc_rsi is None:
        return UNKNOWN

    if lux_trend == "BULLISH" and range_position_pct >= 80:
        if smc_rsi >= 65 and lux_last_event == "SELL":
            return EXHAUSTION

    if lux_trend == "BEARISH" and range_position_pct <= 15:
        if smc_rsi <= 35:
            return EXHAUSTION

    if lux_trend == "BULLISH" and range_position_pct >= 75:
        if smc_rsi >= 60 or lux_last_event == "SELL":
            return EXTENDED

    if lux_trend == "BEARISH" and range_position_pct <= 20:
        if smc_rsi <= 40:
            return EXTENDED

    if lux_days_since_last_event is None:
        return UNKNOWN

    if lux_trend == "BEARISH" and lux_last_event == "SELL":
        if 35 <= range_position_pct <= 70 and smc_rsi >= 40:
            return PULLBACK

    if lux_trend == "BULLISH" and lux_last_event == "BUY":
        if 30 <= range_position_pct <= 65 and smc_rsi <= 60:
            return PULLBACK

    if lux_last_event in {"BUY", "SELL"} and lux_days_since_last_event <= 3:
        if lux_strength == "STRONG":
            if 30 <= range_position_pct <= 65:
                if 45 <= smc_rsi <= 65:
                    return EARLY_TREND

    if lux_strength == "NORMAL" and smc_bias == "NEUTRAL":
        if 20 <= range_position_pct <= 80:
            return RANGE

    return UNKNOWN


def adjust_alignment_for_market_state(
    alignment: str,
    row: Mapping[str, Any],
    market_state: str,
) -> str:
    lux_role = str(row.get("lux_role") or _fallback_lux_role(row) or "")
    smc_role = str(row.get("smc_role") or "")

    if alignment == "conflicted":
        return "conflicted"

    if alignment == "mixed":
        if row.get("lux_trend") == "BEARISH" and row.get("lux_last_event") == "SELL":
            if market_state == PULLBACK and row.get("lux_strength") == "STRONG":
                return "bearish_aligned"
            return BEARISH_WATCHLIST

        if row.get("lux_trend") == "BULLISH" and row.get("lux_last_event") == "BUY":
            if market_state == PULLBACK and row.get("lux_strength") == "STRONG":
                return "bullish_aligned"
            return BULLISH_WATCHLIST

    if alignment == "bullish_aligned" and market_state in {EXTENDED, EXHAUSTION}:
        return BULLISH_WATCHLIST

    if alignment == "bullish_aligned":
        return "bullish_aligned"

    if alignment == "bearish_aligned" and market_state in {EXTENDED, EXHAUSTION}:
        return BEARISH_WATCHLIST

    if alignment == "bearish_aligned":
        return "bearish_aligned"

    if alignment in {"early_bullish", "bullish_watch"}:
        if lux_role.startswith("bearish"):
            return "conflicted"
        return BULLISH_WATCHLIST

    if alignment in {"early_bearish", "bearish_watch"}:
        if lux_role.startswith("bullish"):
            return "conflicted"
        return BEARISH_WATCHLIST

    if alignment == "bullish_trend":
        return "trend_only"

    if alignment == "bearish_trend":
        return "trend_only"

    if market_state == RANGE:
        if smc_role.startswith("bullish") or lux_role.startswith("bullish"):
            return BULLISH_WATCHLIST
        if smc_role.startswith("bearish") or lux_role.startswith("bearish"):
            return BEARISH_WATCHLIST
        return RANGE_WATCHLIST

    return "no_trade"


def classify_action_bucket(
    adjusted_alignment: str,
    market_state: str,
    alignment: str | None = None,
    lux_role: str | None = None,
    smc_role: str | None = None,
    consistency_score: Any = None,
) -> str:
    if adjusted_alignment in {"bullish_aligned", "bearish_aligned"}:
        if market_state in {EARLY_TREND, PULLBACK}:
            if (
                smc_role in {"bullish_trigger", "bearish_trigger"} or smc_role is None
            ) and _consistency_allows_candidate(consistency_score):
                return CANDIDATE
            return WATCHLIST

    if adjusted_alignment in {
        BULLISH_WATCHLIST,
        BEARISH_WATCHLIST,
        RANGE_WATCHLIST,
    }:
        return WATCHLIST

    if adjusted_alignment == "conflicted":
        return NEEDS_REVIEW

    if adjusted_alignment == "trend_only":
        return AVOID

    if market_state in {EXTENDED, EXHAUSTION, RANGE}:
        return WATCHLIST

    if adjusted_alignment == "no_trade":
        return AVOID

    if alignment in {"early_bullish", "early_bearish"}:
        return WATCHLIST

    return NEEDS_REVIEW


def _fallback_lux_role(row: Mapping[str, Any]) -> str | None:
    lux_trend = str(row.get("lux_trend") or "")
    lux_last_event = str(row.get("lux_last_event") or "")

    if lux_trend == "BULLISH" and lux_last_event == "BUY":
        return "bullish_trigger"
    if lux_trend == "BEARISH" and lux_last_event == "SELL":
        return "bearish_trigger"
    if lux_trend == "BULLISH":
        return "bullish_trend"
    if lux_trend == "BEARISH":
        return "bearish_trend"
    return None

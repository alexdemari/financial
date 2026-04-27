from stock_analyzer.enums import Signal


BULLISH_HINTS = {"CALL", "CALL_WATCH"}
BEARISH_HINTS = {"PUT", "PUT_WATCH"}

BULLISH_TRIGGER = "bullish_trigger"
BEARISH_TRIGGER = "bearish_trigger"
BULLISH_TREND = "bullish_trend"
BEARISH_TREND = "bearish_trend"
BULLISH_WATCH = "bullish_watch"
BEARISH_WATCH = "bearish_watch"
NEUTRAL_ROLE = "neutral"

ROLE_BULLISH = {BULLISH_TRIGGER, BULLISH_TREND, BULLISH_WATCH}
ROLE_BEARISH = {BEARISH_TRIGGER, BEARISH_TREND, BEARISH_WATCH}
TRIGGER_ROLES = {BULLISH_TRIGGER, BEARISH_TRIGGER}
WATCH_ROLES = {BULLISH_WATCH, BEARISH_WATCH}
TREND_ROLES = {BULLISH_TREND, BEARISH_TREND}

BULLISH_TRIGGER_CONTEXTS = {
    "bullish_confluence",
    "short_term_bullish_reversal",
}
BEARISH_TRIGGER_CONTEXTS = {
    "bearish_confluence",
    "short_term_bearish_reversal",
}
BULLISH_WATCH_CONTEXTS = {
    "discount_watch",
    "swing_low_watch",
}
BEARISH_WATCH_CONTEXTS = {
    "premium_watch",
    "swing_high_watch",
}


def infer_lux_role(
    *,
    lux_signal: str,
    lux_options_hint: str,
    lux_trend: str,
) -> str:
    side = _hint_side(lux_options_hint)
    if side == "bullish" and lux_signal == "BUY":
        return BULLISH_TRIGGER
    if side == "bearish" and lux_signal == "SELL":
        return BEARISH_TRIGGER
    if lux_trend == "BULLISH":
        return BULLISH_TREND
    if lux_trend == "BEARISH":
        return BEARISH_TREND
    return NEUTRAL_ROLE


def infer_smc_role(
    *,
    smc_signal: str,
    smc_options_hint: str,
    smc_context: str,
    smc_bias: str,
) -> str:
    side = _hint_side(smc_options_hint)
    if side == "bullish" and smc_context in BULLISH_TRIGGER_CONTEXTS:
        return BULLISH_TRIGGER
    if side == "bearish" and smc_context in BEARISH_TRIGGER_CONTEXTS:
        return BEARISH_TRIGGER
    if side == "bullish" and (
        smc_options_hint == "CALL_WATCH" or smc_context in BULLISH_WATCH_CONTEXTS
    ):
        return BULLISH_WATCH
    if side == "bearish" and (
        smc_options_hint == "PUT_WATCH" or smc_context in BEARISH_WATCH_CONTEXTS
    ):
        return BEARISH_WATCH
    if smc_signal == "BUY" and smc_bias == "BULLISH":
        return BULLISH_WATCH
    if smc_signal == "SELL" and smc_bias == "BEARISH":
        return BEARISH_WATCH
    return NEUTRAL_ROLE


def classify_alignment(lux_role: str, smc_role: str) -> str:
    lux_side = role_side(lux_role)

    if smc_role == BULLISH_TRIGGER:
        if lux_side == "bearish":
            return "conflicted"
        if lux_side == "bullish":
            return "bullish_aligned"
        return "early_bullish"

    if smc_role == BEARISH_TRIGGER:
        if lux_side == "bullish":
            return "conflicted"
        if lux_side == "bearish":
            return "bearish_aligned"
        return "early_bearish"

    if smc_role == BULLISH_WATCH:
        if lux_side == "bearish":
            return "conflicted"
        if lux_side == "bullish":
            return "bullish_watch"
        return "early_bullish"

    if smc_role == BEARISH_WATCH:
        if lux_side == "bullish":
            return "conflicted"
        if lux_side == "bearish":
            return "bearish_watch"
        return "early_bearish"

    if lux_role == BULLISH_TRIGGER or lux_role == BULLISH_TREND:
        return "bullish_trend"
    if lux_role == BEARISH_TRIGGER or lux_role == BEARISH_TREND:
        return "bearish_trend"
    return "no_trade"


def compute_consistency_score(
    *,
    lux_role: str,
    smc_role: str,
    lux_signal: str,
    smc_signal: str,
) -> int:
    score = 0
    lux_side = role_side(lux_role)
    smc_side = role_side(smc_role)

    if lux_side is not None and smc_side is not None and lux_side != smc_side:
        return -2

    if smc_role in TRIGGER_ROLES:
        score += 2
    elif smc_role in WATCH_ROLES:
        score += 1

    if lux_role in TRIGGER_ROLES:
        score += 2
    elif lux_role in TREND_ROLES:
        score += 1

    if lux_side is not None and lux_side == smc_side:
        score += 1

    if lux_signal == smc_signal and lux_signal != _signal_label(Signal.HOLD):
        score += 1

    return score


def role_side(role: str | None) -> str | None:
    if role in ROLE_BULLISH:
        return "bullish"
    if role in ROLE_BEARISH:
        return "bearish"
    return None


def _hint_side(options_hint: str) -> str | None:
    if options_hint in BULLISH_HINTS:
        return "bullish"
    if options_hint in BEARISH_HINTS:
        return "bearish"
    return None


def signal_to_label(signal_value) -> str:
    try:
        signal = Signal(int(signal_value))
    except (TypeError, ValueError):
        return str(signal_value)
    return _signal_label(signal)


def _signal_label(signal: Signal) -> str:
    return {
        Signal.BUY: "BUY",
        Signal.SELL: "SELL",
        Signal.HOLD: "HOLD",
    }[signal]

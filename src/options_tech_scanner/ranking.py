from stock_analyzer.enums import Signal


BULLISH_HINTS = {"CALL", "CALL_WATCH"}
BEARISH_HINTS = {"PUT", "PUT_WATCH"}


def classify_alignment(lux_options_hint: str, smc_options_hint: str) -> str:
    lux_side = _hint_side(lux_options_hint)
    smc_side = _hint_side(smc_options_hint)

    if lux_side is None and smc_side is None:
        return "no_trade"
    if lux_side == smc_side == "bullish":
        return "bullish_aligned"
    if lux_side == smc_side == "bearish":
        return "bearish_aligned"
    return "mixed"


def compute_consistency_score(
    lux_options_hint: str,
    smc_options_hint: str,
    lux_signal: str,
    smc_signal: str,
) -> int:
    score = 0

    if lux_options_hint == smc_options_hint and lux_options_hint != "NO_TRADE":
        score += 2

    if lux_signal == smc_signal and lux_signal != _signal_label(Signal.HOLD):
        score += 1

    if _hint_side(lux_options_hint) is not None and _hint_side(
        lux_options_hint
    ) == _hint_side(smc_options_hint):
        score += 1

    if _hints_conflict(lux_options_hint, smc_options_hint):
        score -= 1

    return score


def _hints_conflict(lux_options_hint: str, smc_options_hint: str) -> bool:
    lux_side = _hint_side(lux_options_hint)
    smc_side = _hint_side(smc_options_hint)
    return lux_side is not None and smc_side is not None and lux_side != smc_side


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

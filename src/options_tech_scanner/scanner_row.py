from dataclasses import asdict, dataclass

import pandas as pd

from options_tech_scanner.market_state import (
    adjust_alignment_for_market_state,
    classify_action_bucket,
    classify_market_state,
)
from options_tech_scanner.ranking import (
    classify_alignment,
    compute_consistency_score,
    signal_to_label,
)
from stock_analyzer.analyzer import StockDataAnalyzer


@dataclass
class ScannerRow:
    symbol: str
    close: float | None
    avg_volume_20: float | None
    market_cap: float | None
    ranking_mode: str | None
    lux_signal: str | None
    lux_options_hint: str | None
    lux_context: str | None
    lux_trend: str | None
    lux_strength: str | None
    lux_adx: float | None
    lux_last_event: str | None
    lux_last_event_options_hint: str | None
    lux_last_event_context: str | None
    lux_last_event_date: str | None
    lux_days_since_last_event: int | None
    lux_active_event: str | None
    lux_active_event_options_hint: str | None
    lux_active_event_context: str | None
    lux_active_event_date: str | None
    lux_days_since_active_event: int | None
    smc_signal: str | None
    smc_options_hint: str | None
    smc_context: str | None
    smc_bias: str | None
    smc_range_position_pct: float | None
    smc_rsi: float | None
    smc_last_event: str | None
    smc_last_event_options_hint: str | None
    smc_last_event_context: str | None
    smc_last_event_date: str | None
    smc_days_since_last_event: int | None
    smc_active_event: str | None
    smc_active_event_options_hint: str | None
    smc_active_event_context: str | None
    smc_active_event_date: str | None
    smc_days_since_active_event: int | None
    alignment: str | None
    consistency_score: int | None
    market_state: str | None
    adjusted_alignment: str | None
    action_bucket: str | None
    eligible: bool
    excluded_reason: str | None


def build_scanner_row(
    symbol: str,
    df_slice: pd.DataFrame,
    *,
    ranking_mode: str,
    lux_analyzer: StockDataAnalyzer | None = None,
    smc_analyzer: StockDataAnalyzer | None = None,
    close: float | None = None,
    avg_volume_20: float | None = None,
    market_cap: float | None = None,
) -> dict:
    lux_analyzer = lux_analyzer or StockDataAnalyzer(signal_model="lux")
    smc_analyzer = smc_analyzer or StockDataAnalyzer(signal_model="smc")

    lux_signal = lux_analyzer.generate_signal(symbol, df_slice)
    smc_signal = smc_analyzer.generate_signal(symbol, df_slice)
    lux_historical = lux_analyzer.generate_historical_signals(symbol, df_slice)
    smc_historical = smc_analyzer.generate_historical_signals(symbol, df_slice)

    if lux_signal is None or smc_signal is None:
        raise ValueError(f"Signal generation failed for {symbol}")

    lux_event = _latest_model_event(lux_historical)
    lux_active_event = _active_lux_event(lux_historical)
    smc_event = _latest_model_event(smc_historical)
    smc_active_event = _active_smc_event(smc_historical)

    lux_signal_label = signal_to_label(lux_signal.combined_signal)
    smc_signal_label = signal_to_label(smc_signal.combined_signal)
    ranked_lux_hint, ranked_lux_signal = _rank_inputs(
        ranking_mode=ranking_mode,
        current_options_hint=lux_signal.options_hint,
        current_signal=lux_signal_label,
        latest_event=lux_active_event,
    )
    ranked_smc_hint, ranked_smc_signal = _rank_inputs(
        ranking_mode=ranking_mode,
        current_options_hint=smc_signal.options_hint,
        current_signal=smc_signal_label,
        latest_event=smc_active_event,
    )
    alignment = classify_alignment(ranked_lux_hint, ranked_smc_hint)
    consistency_score = compute_consistency_score(
        lux_options_hint=ranked_lux_hint,
        smc_options_hint=ranked_smc_hint,
        lux_signal=ranked_lux_signal,
        smc_signal=ranked_smc_signal,
    )
    state_inputs = {
        "lux_trend": lux_signal.trend,
        "lux_strength": lux_signal.strength,
        "lux_last_event": lux_event["signal"],
        "lux_days_since_last_event": lux_event["days_since"],
        "smc_bias": smc_signal.bias,
        "smc_range_position_pct": smc_signal.range_position_pct,
        "smc_rsi": smc_signal.rsi,
        "smc_last_event": smc_event["signal"],
        "smc_last_event_context": smc_event["context"],
        "alignment": alignment,
        "consistency_score": consistency_score,
    }
    market_state = classify_market_state(state_inputs)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=alignment,
        row=state_inputs,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(
        adjusted_alignment,
        market_state,
        consistency_score=consistency_score,
    )

    return asdict(
        ScannerRow(
            symbol=symbol,
            close=close if close is not None else float(lux_signal.close_price),
            avg_volume_20=avg_volume_20,
            market_cap=market_cap,
            ranking_mode=ranking_mode,
            lux_signal=lux_signal_label,
            lux_options_hint=lux_signal.options_hint,
            lux_context=_lux_context(lux_signal),
            lux_trend=lux_signal.trend,
            lux_strength=lux_signal.strength,
            lux_adx=lux_signal.adx,
            lux_last_event=lux_event["signal"],
            lux_last_event_options_hint=lux_event["options_hint"],
            lux_last_event_context=lux_event["context"],
            lux_last_event_date=lux_event["date"],
            lux_days_since_last_event=lux_event["days_since"],
            lux_active_event=lux_active_event["signal"],
            lux_active_event_options_hint=lux_active_event["options_hint"],
            lux_active_event_context=lux_active_event["context"],
            lux_active_event_date=lux_active_event["date"],
            lux_days_since_active_event=lux_active_event["days_since"],
            smc_signal=smc_signal_label,
            smc_options_hint=smc_signal.options_hint,
            smc_context=_smc_context(smc_signal),
            smc_bias=smc_signal.bias,
            smc_range_position_pct=smc_signal.range_position_pct,
            smc_rsi=smc_signal.rsi,
            smc_last_event=smc_event["signal"],
            smc_last_event_options_hint=smc_event["options_hint"],
            smc_last_event_context=smc_event["context"],
            smc_last_event_date=smc_event["date"],
            smc_days_since_last_event=smc_event["days_since"],
            smc_active_event=smc_active_event["signal"],
            smc_active_event_options_hint=smc_active_event["options_hint"],
            smc_active_event_context=smc_active_event["context"],
            smc_active_event_date=smc_active_event["date"],
            smc_days_since_active_event=smc_active_event["days_since"],
            alignment=alignment,
            consistency_score=consistency_score,
            market_state=market_state,
            adjusted_alignment=adjusted_alignment,
            action_bucket=action_bucket,
            eligible=True,
            excluded_reason=None,
        )
    )


def _lux_context(signal) -> str:
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


def _smc_context(signal) -> str:
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


def _latest_model_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    if historical.empty:
        return _empty_event()

    event_rows = historical[_event_mask(historical)]
    if event_rows.empty:
        return _empty_event()

    return _event_from_row(event_rows.iloc[-1], historical)


def _event_mask(historical: pd.DataFrame) -> pd.Series:
    if "options_hint" in historical.columns:
        return historical["options_hint"].fillna("NO_TRADE") != "NO_TRADE"
    return historical["combined_signal"] != 0


def _empty_event() -> dict[str, str | int | None]:
    return {
        "signal": None,
        "options_hint": None,
        "context": None,
        "date": None,
        "days_since": None,
    }


def _active_lux_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    priority_contexts = (
        ("trend_confirmation_buy", "trend_confirmation_sell"),
        ("contrarian_reversal_buy", "contrarian_reversal_sell"),
    )
    return _latest_event_by_priority(historical, priority_contexts)


def _active_smc_event(historical: pd.DataFrame) -> dict[str, str | int | None]:
    priority_contexts = (
        ("short_term_bullish_reversal", "short_term_bearish_reversal"),
        ("bullish_confluence", "bearish_confluence"),
    )
    return _latest_event_by_priority(historical, priority_contexts)


def _latest_event_by_priority(
    historical: pd.DataFrame,
    priority_contexts: tuple[tuple[str, str], ...],
) -> dict[str, str | int | None]:
    if historical.empty or "signal_context" not in historical.columns:
        return _empty_event()

    for bullish_context, bearish_context in priority_contexts:
        matching = historical[
            historical["signal_context"].isin([bullish_context, bearish_context])
        ]
        if not matching.empty:
            return _event_from_row(matching.iloc[-1], historical)

    return _empty_event()


def _event_from_row(
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


def _rank_inputs(
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

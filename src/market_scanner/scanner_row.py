from dataclasses import asdict

import pandas as pd

from market_scanner.event_state import (
    active_lux_event,
    active_smc_event,
    latest_model_event,
    lux_context,
    lux_signal_from_history,
    rank_inputs,
    smc_context,
    smc_signal_from_history,
)
from market_scanner.market_state import (
    adjust_alignment_for_market_state,
    classify_action_bucket,
    classify_market_state,
)
from market_scanner.models import ScannerRow
from market_scanner.ranking import (
    classify_alignment,
    compute_consistency_score,
    infer_lux_role,
    infer_smc_role,
    signal_to_label,
)
from stock_analyzer.analyzer import StockDataAnalyzer


def build_scanner_row(
    symbol: str,
    df_slice: pd.DataFrame,
    *,
    ranking_mode: str,
    lux_analyzer: StockDataAnalyzer | None = None,
    smc_analyzer: StockDataAnalyzer | None = None,
    close: float | None = None,
    avg_volume_20: float | None = None,
    avg_dollar_volume_20: float | None = None,
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

    return _assemble_scanner_row(
        symbol=symbol,
        lux_signal=lux_signal,
        smc_signal=smc_signal,
        lux_historical=lux_historical,
        smc_historical=smc_historical,
        ranking_mode=ranking_mode,
        close=close,
        avg_volume_20=avg_volume_20,
        avg_dollar_volume_20=avg_dollar_volume_20,
        market_cap=market_cap,
    )


def build_scanner_row_from_history(
    symbol: str,
    *,
    close: float,
    lux_historical: pd.DataFrame,
    smc_historical: pd.DataFrame,
    index: int,
    ranking_mode: str,
    avg_volume_20: float | None = None,
    avg_dollar_volume_20: float | None = None,
    market_cap: float | None = None,
    lux_event_state: dict[str, dict[str, str | int | None]] | None = None,
    smc_event_state: dict[str, dict[str, str | int | None]] | None = None,
) -> dict:
    lux_signal = lux_signal_from_history(symbol, lux_historical.iloc[index])
    smc_signal = smc_signal_from_history(symbol, smc_historical.iloc[index])

    if lux_event_state is None or smc_event_state is None:
        lux_historical = lux_historical.iloc[: index + 1]
        smc_historical = smc_historical.iloc[: index + 1]

    return _assemble_scanner_row(
        symbol=symbol,
        lux_signal=lux_signal,
        smc_signal=smc_signal,
        lux_historical=lux_historical,
        smc_historical=smc_historical,
        ranking_mode=ranking_mode,
        close=close,
        avg_volume_20=avg_volume_20,
        avg_dollar_volume_20=avg_dollar_volume_20,
        market_cap=market_cap,
        lux_event_state=lux_event_state,
        smc_event_state=smc_event_state,
    )


def _assemble_scanner_row(
    *,
    symbol: str,
    lux_signal,
    smc_signal,
    lux_historical: pd.DataFrame,
    smc_historical: pd.DataFrame,
    ranking_mode: str,
    close: float | None,
    avg_volume_20: float | None,
    avg_dollar_volume_20: float | None,
    market_cap: float | None,
    lux_event_state: dict[str, dict[str, str | int | None]] | None = None,
    smc_event_state: dict[str, dict[str, str | int | None]] | None = None,
) -> dict:
    lux_event = (
        lux_event_state["latest"]
        if lux_event_state is not None
        else latest_model_event(lux_historical)
    )
    lux_active = (
        lux_event_state["active"]
        if lux_event_state is not None
        else active_lux_event(lux_historical)
    )
    smc_event = (
        smc_event_state["latest"]
        if smc_event_state is not None
        else latest_model_event(smc_historical)
    )
    smc_active = (
        smc_event_state["active"]
        if smc_event_state is not None
        else active_smc_event(smc_historical)
    )
    selected_lux_event = _selected_state_event(ranking_mode, lux_event, lux_active)
    selected_smc_event = _selected_state_event(ranking_mode, smc_event, smc_active)

    lux_signal_label = signal_to_label(lux_signal.combined_signal)
    smc_signal_label = signal_to_label(smc_signal.combined_signal)
    ranked_lux_hint, ranked_lux_signal = rank_inputs(
        ranking_mode=ranking_mode,
        current_options_hint=lux_signal.options_hint,
        current_signal=lux_signal_label,
        latest_event=lux_active,
    )
    ranked_smc_hint, ranked_smc_signal = rank_inputs(
        ranking_mode=ranking_mode,
        current_options_hint=smc_signal.options_hint,
        current_signal=smc_signal_label,
        latest_event=smc_active,
    )
    ranked_smc_context = _selected_rank_context(
        ranking_mode=ranking_mode,
        current_context=smc_context(smc_signal),
        latest_event=smc_active,
    )
    lux_role = infer_lux_role(
        lux_signal=ranked_lux_signal,
        lux_options_hint=ranked_lux_hint,
        lux_trend=lux_signal.trend,
    )
    smc_role = infer_smc_role(
        smc_signal=ranked_smc_signal,
        smc_options_hint=ranked_smc_hint,
        smc_context=ranked_smc_context,
        smc_bias=smc_signal.bias,
    )

    alignment = classify_alignment(lux_role, smc_role)
    consistency_score = compute_consistency_score(
        lux_role=lux_role,
        smc_role=smc_role,
        lux_signal=ranked_lux_signal,
        smc_signal=ranked_smc_signal,
    )
    state_inputs = {
        "lux_trend": lux_signal.trend,
        "lux_strength": lux_signal.strength,
        "lux_last_event": selected_lux_event["signal"],
        "lux_days_since_last_event": selected_lux_event["days_since"],
        "smc_bias": smc_signal.bias,
        "smc_range_position_pct": smc_signal.range_position_pct,
        "smc_rsi": smc_signal.rsi,
        "smc_last_event": selected_smc_event["signal"],
        "smc_last_event_context": selected_smc_event["context"],
        "alignment": alignment,
        "lux_role": lux_role,
        "smc_role": smc_role,
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
        alignment=alignment,
        lux_role=lux_role,
        smc_role=smc_role,
        consistency_score=consistency_score,
    )

    return asdict(
        ScannerRow(
            symbol=symbol,
            close=close if close is not None else float(lux_signal.close_price),
            avg_volume_20=avg_volume_20,
            avg_dollar_volume_20=avg_dollar_volume_20,
            market_cap=market_cap,
            ranking_mode=ranking_mode,
            lux_role=lux_role,
            lux_signal=lux_signal_label,
            lux_options_hint=lux_signal.options_hint,
            lux_context=lux_context(lux_signal),
            lux_trend=lux_signal.trend,
            lux_strength=lux_signal.strength,
            lux_adx=lux_signal.adx,
            lux_last_event=lux_event["signal"],
            lux_last_event_options_hint=lux_event["options_hint"],
            lux_last_event_context=lux_event["context"],
            lux_last_event_date=lux_event["date"],
            lux_days_since_last_event=lux_event["days_since"],
            lux_active_event=lux_active["signal"],
            lux_active_event_options_hint=lux_active["options_hint"],
            lux_active_event_context=lux_active["context"],
            lux_active_event_date=lux_active["date"],
            lux_days_since_active_event=lux_active["days_since"],
            smc_role=smc_role,
            smc_signal=smc_signal_label,
            smc_options_hint=smc_signal.options_hint,
            smc_context=smc_context(smc_signal),
            smc_bias=smc_signal.bias,
            smc_range_position_pct=smc_signal.range_position_pct,
            smc_rsi=smc_signal.rsi,
            smc_last_event=smc_event["signal"],
            smc_last_event_options_hint=smc_event["options_hint"],
            smc_last_event_context=smc_event["context"],
            smc_last_event_date=smc_event["date"],
            smc_days_since_last_event=smc_event["days_since"],
            smc_active_event=smc_active["signal"],
            smc_active_event_options_hint=smc_active["options_hint"],
            smc_active_event_context=smc_active["context"],
            smc_active_event_date=smc_active["date"],
            smc_days_since_active_event=smc_active["days_since"],
            alignment=alignment,
            consistency_score=consistency_score,
            market_state=market_state,
            adjusted_alignment=adjusted_alignment,
            action_bucket=action_bucket,
            eligible=True,
            excluded_reason=None,
        )
    )


def _selected_state_event(
    ranking_mode: str,
    latest_event: dict[str, str | int | None],
    active_event: dict[str, str | int | None],
) -> dict[str, str | int | None]:
    if ranking_mode == "recent-event" and active_event["signal"] is not None:
        return active_event
    return latest_event


def _selected_rank_context(
    *,
    ranking_mode: str,
    current_context: str,
    latest_event: dict[str, str | int | None],
) -> str:
    if ranking_mode == "recent-event" and latest_event["context"] is not None:
        return str(latest_event["context"])
    return current_context


_smc_context = smc_context

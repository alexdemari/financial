import argparse
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from options_tech_scanner.eligibility import (
    MIN_HISTORY_ROWS,
    EligibilityResult,
    evaluate_symbol_eligibility,
    load_symbol_csv,
)
from options_tech_scanner.market_state import (
    AVOID,
    UNKNOWN,
    adjust_alignment_for_market_state,
    classify_action_bucket,
    classify_market_state,
)
from options_tech_scanner.ranking import (
    classify_alignment,
    compute_consistency_score,
    signal_to_label,
)
from options_tech_scanner.report_writer import render_top_n_summary, write_csv_report
from options_tech_scanner.universe_loader import load_universe
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


def scan_universe(
    universe_file: str | Path,
    data_dir: str | Path,
    min_market_cap: float,
    min_avg_volume_20: float,
    top: int,
    output: str | Path,
    ranking_mode: str = "snapshot",
    min_history_rows: int = MIN_HISTORY_ROWS,
) -> tuple[pd.DataFrame, Path]:
    universe = load_universe(universe_file)
    rows: list[dict] = []

    lux_analyzer = StockDataAnalyzer(signal_model="lux")
    smc_analyzer = StockDataAnalyzer(signal_model="smc")

    for entry in universe.itertuples(index=False):
        symbol = str(entry.symbol)
        market_cap = float(entry.market_cap) if pd.notna(entry.market_cap) else None

        try:
            df = load_symbol_csv(data_dir, symbol)
        except FileNotFoundError:
            eligibility = evaluate_symbol_eligibility(
                market_cap=market_cap,
                df=None,
                min_market_cap=min_market_cap,
                min_avg_volume_20=min_avg_volume_20,
                min_history_rows=min_history_rows,
            )
            rows.append(
                _build_excluded_row(
                    symbol,
                    market_cap,
                    eligibility,
                    ranking_mode=ranking_mode,
                )
            )
            continue
        except Exception:
            rows.append(
                asdict(
                    ScannerRow(
                        symbol=symbol,
                        close=None,
                        avg_volume_20=None,
                        market_cap=market_cap,
                        ranking_mode=ranking_mode,
                        lux_signal=None,
                        lux_options_hint=None,
                        lux_context=None,
                        lux_trend=None,
                        lux_strength=None,
                        lux_adx=None,
                        lux_last_event=None,
                        lux_last_event_options_hint=None,
                        lux_last_event_context=None,
                        lux_last_event_date=None,
                        lux_days_since_last_event=None,
                        lux_active_event=None,
                        lux_active_event_options_hint=None,
                        lux_active_event_context=None,
                        lux_active_event_date=None,
                        lux_days_since_active_event=None,
                        smc_signal=None,
                        smc_options_hint=None,
                        smc_context=None,
                        smc_bias=None,
                        smc_range_position_pct=None,
                        smc_rsi=None,
                        smc_last_event=None,
                        smc_last_event_options_hint=None,
                        smc_last_event_context=None,
                        smc_last_event_date=None,
                        smc_days_since_last_event=None,
                        smc_active_event=None,
                        smc_active_event_options_hint=None,
                        smc_active_event_context=None,
                        smc_active_event_date=None,
                        smc_days_since_active_event=None,
                        alignment=None,
                        consistency_score=None,
                        market_state=UNKNOWN,
                        adjusted_alignment="no_trade",
                        action_bucket=AVOID,
                        eligible=False,
                        excluded_reason="analysis_failed",
                    )
                )
            )
            continue

        eligibility = evaluate_symbol_eligibility(
            market_cap=market_cap,
            df=df,
            min_market_cap=min_market_cap,
            min_avg_volume_20=min_avg_volume_20,
            min_history_rows=min_history_rows,
        )
        if not eligibility.eligible:
            rows.append(
                _build_excluded_row(
                    symbol,
                    market_cap,
                    eligibility,
                    ranking_mode=ranking_mode,
                )
            )
            continue

        try:
            rows.append(
                _build_eligible_row(
                    symbol=symbol,
                    market_cap=market_cap,
                    avg_volume_20=eligibility.avg_volume_20,
                    close=eligibility.close,
                    df=df,
                    lux_analyzer=lux_analyzer,
                    smc_analyzer=smc_analyzer,
                    ranking_mode=ranking_mode,
                )
            )
        except Exception:
            rows.append(
                asdict(
                    ScannerRow(
                        symbol=symbol,
                        close=eligibility.close,
                        avg_volume_20=eligibility.avg_volume_20,
                        market_cap=market_cap,
                        ranking_mode=ranking_mode,
                        lux_signal=None,
                        lux_options_hint=None,
                        lux_context=None,
                        lux_trend=None,
                        lux_strength=None,
                        lux_adx=None,
                        lux_last_event=None,
                        lux_last_event_options_hint=None,
                        lux_last_event_context=None,
                        lux_last_event_date=None,
                        lux_days_since_last_event=None,
                        lux_active_event=None,
                        lux_active_event_options_hint=None,
                        lux_active_event_context=None,
                        lux_active_event_date=None,
                        lux_days_since_active_event=None,
                        smc_signal=None,
                        smc_options_hint=None,
                        smc_context=None,
                        smc_bias=None,
                        smc_range_position_pct=None,
                        smc_rsi=None,
                        smc_last_event=None,
                        smc_last_event_options_hint=None,
                        smc_last_event_context=None,
                        smc_last_event_date=None,
                        smc_days_since_last_event=None,
                        smc_active_event=None,
                        smc_active_event_options_hint=None,
                        smc_active_event_context=None,
                        smc_active_event_date=None,
                        smc_days_since_active_event=None,
                        alignment=None,
                        consistency_score=None,
                        market_state=UNKNOWN,
                        adjusted_alignment="no_trade",
                        action_bucket=AVOID,
                        eligible=False,
                        excluded_reason="analysis_failed",
                    )
                )
            )

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df = result_df.sort_values(
            ["eligible", "consistency_score", "symbol"],
            ascending=[False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    output_path = write_csv_report(result_df, output)
    print(render_top_n_summary(result_df[result_df["eligible"]], top))
    print(f"\nExported: {output_path}")
    return result_df, output_path


def _build_excluded_row(
    symbol: str,
    market_cap: float | None,
    eligibility: EligibilityResult,
    ranking_mode: str = "snapshot",
) -> dict:
    return asdict(
        ScannerRow(
            symbol=symbol,
            close=eligibility.close,
            avg_volume_20=eligibility.avg_volume_20,
            market_cap=market_cap,
            ranking_mode=ranking_mode,
            lux_signal=None,
            lux_options_hint=None,
            lux_context=None,
            lux_trend=None,
            lux_strength=None,
            lux_adx=None,
            lux_last_event=None,
            lux_last_event_options_hint=None,
            lux_last_event_context=None,
            lux_last_event_date=None,
            lux_days_since_last_event=None,
            lux_active_event=None,
            lux_active_event_options_hint=None,
            lux_active_event_context=None,
            lux_active_event_date=None,
            lux_days_since_active_event=None,
            smc_signal=None,
            smc_options_hint=None,
            smc_context=None,
            smc_bias=None,
            smc_range_position_pct=None,
            smc_rsi=None,
            smc_last_event=None,
            smc_last_event_options_hint=None,
            smc_last_event_context=None,
            smc_last_event_date=None,
            smc_days_since_last_event=None,
            smc_active_event=None,
            smc_active_event_options_hint=None,
            smc_active_event_context=None,
            smc_active_event_date=None,
            smc_days_since_active_event=None,
            alignment=None,
            consistency_score=None,
            market_state=UNKNOWN,
            adjusted_alignment="no_trade",
            action_bucket=AVOID,
            eligible=False,
            excluded_reason=eligibility.excluded_reason,
        )
    )


def _build_eligible_row(
    symbol: str,
    market_cap: float | None,
    avg_volume_20: float | None,
    close: float | None,
    df: pd.DataFrame,
    lux_analyzer: StockDataAnalyzer,
    smc_analyzer: StockDataAnalyzer,
    ranking_mode: str,
) -> dict:
    lux_signal = lux_analyzer.generate_signal(symbol, df)
    smc_signal = smc_analyzer.generate_signal(symbol, df)
    lux_historical = lux_analyzer.generate_historical_signals(symbol, df)
    smc_historical = smc_analyzer.generate_historical_signals(symbol, df)

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
    v2_row = {
        "lux_trend": lux_signal.trend,
        "lux_strength": lux_signal.strength,
        "lux_last_event": lux_event["signal"],
        "lux_days_since_last_event": lux_event["days_since"],
        "lux_active_event": lux_active_event["signal"],
        "lux_days_since_active_event": lux_active_event["days_since"],
        "smc_bias": smc_signal.bias,
        "smc_range_position_pct": smc_signal.range_position_pct,
        "smc_rsi": smc_signal.rsi,
        "smc_last_event": smc_event["signal"],
        "smc_last_event_context": smc_event["context"],
        "smc_days_since_last_event": smc_event["days_since"],
        "alignment": alignment,
        "consistency_score": consistency_score,
    }
    market_state = classify_market_state(v2_row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=alignment,
        row=v2_row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Local Universe Scanner V1")
    parser.add_argument(
        "--universe-file", required=True, help="Local universe metadata file"
    )
    parser.add_argument(
        "--data-dir", required=True, help="Directory with local OHLC CSV files"
    )
    parser.add_argument(
        "--min-market-cap",
        type=float,
        default=1_000_000_000,
        help="Minimum market cap eligibility filter",
    )
    parser.add_argument(
        "--min-avg-volume-20",
        type=float,
        default=1_000_000,
        help="Minimum average daily volume over the last 20 sessions",
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Top-N rows printed to terminal"
    )
    parser.add_argument(
        "--ranking-mode",
        choices=["snapshot", "recent-event"],
        default="snapshot",
        help=(
            "Ranking basis: current Lux/SMC snapshot or the model's active "
            "directional event from historical signals"
        ),
    )
    parser.add_argument("--output", required=True, help="CSV output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scan_universe(
        universe_file=args.universe_file,
        data_dir=args.data_dir,
        min_market_cap=args.min_market_cap,
        min_avg_volume_20=args.min_avg_volume_20,
        top=args.top,
        output=args.output,
        ranking_mode=args.ranking_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

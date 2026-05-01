import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
from market_scanner.event_state import smc_context

from market_scanner.eligibility import (
    MIN_HISTORY_ROWS,
    EligibilityResult,
    evaluate_symbol_eligibility,
)
from market_scanner.market_state import AVOID, UNKNOWN
from market_scanner.models import ScannerRow
from market_scanner.pipeline import (
    create_analyzers,
    iter_symbol_data,
    load_selected_universe,
)
from market_scanner.report_writer import (
    render_top_n_summary,
    sort_scanner_results,
    write_csv_report,
)
from market_scanner.scanner_row import build_scanner_row
from stock_analyzer.analyzer import StockDataAnalyzer

_smc_context = smc_context


@dataclass
class _ScanWorkerArgs:
    symbol: str
    market_cap: float | None
    df: pd.DataFrame | None
    load_error: str | None
    analysis_bars: int | None
    ranking_mode: str
    min_market_cap: float
    min_avg_volume_20: float
    min_avg_dollar_volume_20: float
    min_history_rows: int


def _scan_symbol_worker(args: _ScanWorkerArgs) -> dict:
    symbol = args.symbol
    market_cap = args.market_cap

    if args.load_error == "missing_csv":
        eligibility = evaluate_symbol_eligibility(
            market_cap=market_cap,
            df=None,
            min_market_cap=args.min_market_cap,
            min_avg_volume_20=args.min_avg_volume_20,
            min_avg_dollar_volume_20=args.min_avg_dollar_volume_20,
            min_history_rows=args.min_history_rows,
        )
        return _build_excluded_row(
            symbol, market_cap, eligibility, ranking_mode=args.ranking_mode
        )

    if args.load_error is not None or args.df is None:
        return _build_analysis_failed_row(symbol, market_cap, args.ranking_mode)

    analysis_df = _analysis_window(args.df, args.analysis_bars)
    eligibility = evaluate_symbol_eligibility(
        market_cap=market_cap,
        df=analysis_df,
        min_market_cap=args.min_market_cap,
        min_avg_volume_20=args.min_avg_volume_20,
        min_avg_dollar_volume_20=args.min_avg_dollar_volume_20,
        min_history_rows=args.min_history_rows,
    )
    if not eligibility.eligible:
        return _build_excluded_row(
            symbol, market_cap, eligibility, ranking_mode=args.ranking_mode
        )

    try:
        return build_scanner_row(
            symbol=symbol,
            df_slice=analysis_df,
            ranking_mode=args.ranking_mode,
            close=eligibility.close,
            avg_volume_20=eligibility.avg_volume_20,
            avg_dollar_volume_20=eligibility.avg_dollar_volume_20,
            market_cap=market_cap,
        )
    except Exception as exc:
        row = _build_analysis_failed_row(
            symbol, market_cap, args.ranking_mode, error=exc
        )
        row["_error_detail"] = f"{type(exc).__name__}: {exc}"
        return row


def scan_universe(
    universe_file: str | Path,
    data_dir: str | Path,
    min_market_cap: float,
    min_avg_volume_20: float,
    top: int,
    output: str | Path,
    ranking_mode: str = "snapshot",
    min_history_rows: int = MIN_HISTORY_ROWS,
    min_avg_dollar_volume_20: float = 0,
    analysis_bars: int | None = None,
    sort_by: str = "scanner",
    workers: int = 1,
) -> tuple[pd.DataFrame, Path]:
    universe = load_selected_universe(universe_file)
    rows: list[dict] = []

    if workers > 1:
        worker_args_list = [
            _ScanWorkerArgs(
                symbol=sd.symbol,
                market_cap=sd.market_cap,
                df=sd.df,
                load_error=sd.load_error,
                analysis_bars=analysis_bars,
                ranking_mode=ranking_mode,
                min_market_cap=min_market_cap,
                min_avg_volume_20=min_avg_volume_20,
                min_avg_dollar_volume_20=min_avg_dollar_volume_20,
                min_history_rows=min_history_rows,
            )
            for sd in iter_symbol_data(universe, data_dir)
        ]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            raw_rows: list[dict] = list(pool.map(_scan_symbol_worker, worker_args_list))
        for row in raw_rows:
            error_detail = row.pop("_error_detail", None)
            if error_detail is not None:
                print(
                    f"Analysis failed for {row['symbol']}: {error_detail}",
                    file=sys.stderr,
                )
            rows.append(row)
    else:
        analyzers = create_analyzers(StockDataAnalyzer)

        for symbol_data in iter_symbol_data(universe, data_dir):
            symbol = symbol_data.symbol
            market_cap = symbol_data.market_cap
            df = symbol_data.df

            if symbol_data.load_error == "missing_csv":
                eligibility = evaluate_symbol_eligibility(
                    market_cap=market_cap,
                    df=None,
                    min_market_cap=min_market_cap,
                    min_avg_volume_20=min_avg_volume_20,
                    min_avg_dollar_volume_20=min_avg_dollar_volume_20,
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

            if symbol_data.load_error is not None or df is None:
                rows.append(
                    _build_analysis_failed_row(symbol, market_cap, ranking_mode)
                )
                continue

            analysis_df = _analysis_window(df, analysis_bars)
            eligibility = evaluate_symbol_eligibility(
                market_cap=market_cap,
                df=analysis_df,
                min_market_cap=min_market_cap,
                min_avg_volume_20=min_avg_volume_20,
                min_avg_dollar_volume_20=min_avg_dollar_volume_20,
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
                    build_scanner_row(
                        symbol=symbol,
                        df_slice=analysis_df,
                        ranking_mode=ranking_mode,
                        lux_analyzer=analyzers.lux_analyzer,
                        smc_analyzer=analyzers.smc_analyzer,
                        close=eligibility.close,
                        avg_volume_20=eligibility.avg_volume_20,
                        avg_dollar_volume_20=eligibility.avg_dollar_volume_20,
                        market_cap=market_cap,
                    )
                )
            except Exception as exc:
                print(
                    f"Analysis failed for {symbol}: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                rows.append(
                    _build_analysis_failed_row(
                        symbol,
                        market_cap,
                        ranking_mode,
                        error=exc,
                    )
                )

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df = sort_scanner_results(result_df, sort_by=sort_by).reset_index(
            drop=True
        )

    output_path = write_csv_report(result_df, output)
    print(render_top_n_summary(result_df[result_df["eligible"]], top, sort_by=sort_by))
    print(f"\nExported: {output_path}")
    return result_df, output_path


def _analysis_window(df: pd.DataFrame, analysis_bars: int | None) -> pd.DataFrame:
    if analysis_bars is None:
        return df
    if analysis_bars <= 0:
        raise ValueError("analysis_bars must be greater than zero")
    return df.tail(analysis_bars)


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
            avg_dollar_volume_20=eligibility.avg_dollar_volume_20,
            market_cap=market_cap,
            ranking_mode=ranking_mode,
            lux_role=None,
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
            smc_role=None,
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


def _build_analysis_failed_row(
    symbol: str,
    market_cap: float | None,
    ranking_mode: str,
    error: Exception | None = None,
) -> dict:
    excluded_reason = "analysis_failed"
    if error is not None:
        excluded_reason = f"analysis_failed:{type(error).__name__}"

    return asdict(
        ScannerRow(
            symbol=symbol,
            close=None,
            avg_volume_20=None,
            avg_dollar_volume_20=None,
            market_cap=market_cap,
            ranking_mode=ranking_mode,
            lux_role=None,
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
            smc_role=None,
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
            excluded_reason=excluded_reason,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Market Scanner")
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
        "--min-avg-dollar-volume-20",
        type=float,
        default=0,
        help="Minimum average dollar volume over the last 20 sessions",
    )
    parser.add_argument(
        "--analysis-bars",
        type=int,
        default=None,
        help="Limit signal analysis to the most recent N bars",
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
    parser.add_argument(
        "--sort-by",
        choices=["scanner", "smc-recent"],
        default="scanner",
        help="Sort basis for CSV and terminal output",
    )
    parser.add_argument("--output", required=True, help="CSV output path")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel worker processes (default: 1)",
    )
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
        min_avg_dollar_volume_20=args.min_avg_dollar_volume_20,
        analysis_bars=args.analysis_bars,
        sort_by=args.sort_by,
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

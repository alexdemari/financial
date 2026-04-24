import argparse
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from options_tech_scanner.eligibility import (
    MIN_HISTORY_ROWS,
    EligibilityResult,
    evaluate_symbol_eligibility,
    load_symbol_csv,
)
from options_tech_scanner.market_state import AVOID, UNKNOWN
from options_tech_scanner.report_writer import render_top_n_summary, write_csv_report
from options_tech_scanner import scanner_row as scanner_row_module
from options_tech_scanner.scanner_row import ScannerRow, build_scanner_row
from options_tech_scanner.universe_loader import load_universe
from stock_analyzer.analyzer import StockDataAnalyzer

_smc_context = scanner_row_module._smc_context


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
            rows.append(_build_analysis_failed_row(symbol, market_cap, ranking_mode))
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
                build_scanner_row(
                    symbol=symbol,
                    df_slice=df,
                    ranking_mode=ranking_mode,
                    lux_analyzer=lux_analyzer,
                    smc_analyzer=smc_analyzer,
                    close=eligibility.close,
                    avg_volume_20=eligibility.avg_volume_20,
                    market_cap=market_cap,
                )
            )
        except Exception:
            rows.append(_build_analysis_failed_row(symbol, market_cap, ranking_mode))

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


def _build_analysis_failed_row(
    symbol: str,
    market_cap: float | None,
    ranking_mode: str,
) -> dict:
    return asdict(
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

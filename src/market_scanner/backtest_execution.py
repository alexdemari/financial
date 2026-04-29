import argparse
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pandas as pd

from market_scanner.backtest import prepare_backtest_df
from market_scanner.eligibility import MIN_HISTORY_ROWS
from market_scanner.exits import (
    exit_after_n_bars,
    exit_on_alignment_break,
    exit_on_bucket_downgrade,
    exit_on_late_state,
    exit_on_opposite_signal,
)
from market_scanner.pipeline import (
    create_analyzers,
    iter_symbol_data,
    load_selected_universe,
)
from market_scanner.report_writer import write_csv_report
from market_scanner.scanner_row import build_scanner_row_from_history
from market_scanner.trades import (
    Trade,
    TradeSide,
    build_trade,
    compute_trade_excursions,
    summarize_trade_records,
    summarize_symbol_trade_records,
    trade_to_record,
)
from stock_analyzer.analyzer import StockDataAnalyzer

DEFAULT_MIN_BARS = 120
SCANNER_ROW_MIN_BARS = MIN_HISTORY_ROWS
DEFAULT_REPORTS_DIR = "reports/market_scanner"
ALL_EXIT_RULES = (
    "alignment_break",
    "bucket_downgrade",
    "late_state",
    "opposite_signal",
    "bars_5",
    "bars_10",
    "bars_20",
)
EXIT_RULE_CHOICES = (*ALL_EXIT_RULES, "all")
COMPARISON_COLUMNS = [
    "rank",
    "qualified",
    "qualification_reason",
    "exit_rule",
    "ranking_mode",
    "side",
    "entry_alignment",
    "total_trades",
    "win_rate",
    "loss_rate",
    "avg_directional_return",
    "median_directional_return",
    "expectancy",
    "profit_factor",
    "avg_mfe",
    "avg_mae",
    "avg_bars_held",
    "best_trade",
    "worst_trade",
]
SYMBOL_COMPARISON_COLUMNS = [
    "symbol",
    "exit_rule",
    "ranking_mode",
    "side",
    "entry_alignment",
    "total_trades",
    "win_rate",
    "loss_rate",
    "avg_return",
    "median_return",
    "avg_directional_return",
    "median_directional_return",
    "avg_mfe",
    "avg_mae",
    "avg_bars_held",
    "expectancy",
    "profit_factor",
    "best_trade",
    "worst_trade",
]
RECOMMENDATION_COLUMNS = [
    "scope",
    "symbol",
    "side",
    "recommended_exit_rule",
    "qualified",
    "qualification_reason",
    "ranking_mode",
    "entry_alignment",
    "total_trades",
    "win_rate",
    "loss_rate",
    "avg_directional_return",
    "median_directional_return",
    "expectancy",
    "profit_factor",
    "avg_mfe",
    "avg_mae",
    "avg_bars_held",
    "best_trade",
    "worst_trade",
]
WORST_TRADES_COLUMNS = [
    "report_reason",
    "symbol",
    "side",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "bars_held",
    "entry_alignment",
    "exit_reason",
    "raw_return",
    "directional_return",
    "mfe",
    "mae",
    "exit_rule",
    "ranking_mode",
]


@dataclass
class OpenPosition:
    symbol: str
    side: TradeSide
    entry_index: int
    entry_date: str
    entry_price: float
    entry_alignment: str


@dataclass(frozen=True)
class ExecutionBar:
    index: int
    date: str
    close: float
    row: dict


@dataclass(frozen=True)
class PreparedSymbolExecutionData:
    symbol: str
    df: pd.DataFrame
    bars: list[ExecutionBar]
    high_column: str
    low_column: str


def backtest_execution_universe(
    *,
    universe_file: str | Path,
    data_dir: str | Path,
    ranking_mode: str,
    exit_rule: str,
    min_bars: int = DEFAULT_MIN_BARS,
    output_trades: str | Path = f"{DEFAULT_REPORTS_DIR}/execution_trades.csv",
    output_summary: str | Path = f"{DEFAULT_REPORTS_DIR}/execution_summary.csv",
    output_comparison: str | Path = (
        f"{DEFAULT_REPORTS_DIR}/execution_rule_comparison.csv"
    ),
    output_symbol_comparison: str | Path = (
        f"{DEFAULT_REPORTS_DIR}/execution_symbol_comparison.csv"
    ),
    output_recommendations: str | Path = (
        f"{DEFAULT_REPORTS_DIR}/execution_recommended_rules.csv"
    ),
    output_worst_trades: str
    | Path = f"{DEFAULT_REPORTS_DIR}/execution_worst_trades.csv",
    min_trades: int = 20,
    symbols: list[str] | None = None,
    progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = load_selected_universe(universe_file, symbols=symbols)
    analyzers = create_analyzers(StockDataAnalyzer)
    trade_records: list[dict] = []
    exit_rules = resolve_exit_rules(exit_rule)
    total_symbols = len(universe)
    start_time = perf_counter()
    processed_symbols = 0

    def _transform_df(df: pd.DataFrame) -> pd.DataFrame:
        return prepare_backtest_df(df=df.sort_index())

    for symbol_data in iter_symbol_data(universe, data_dir, transform_df=_transform_df):
        symbol_start = perf_counter()
        processed_symbols += 1
        if symbol_data.load_error is not None or symbol_data.df is None:
            if progress:
                _print_progress(
                    processed_symbols=processed_symbols,
                    total_symbols=total_symbols,
                    symbol=symbol_data.symbol,
                    start_time=start_time,
                    symbol_start=symbol_start,
                    status=symbol_data.load_error,
                )
            continue

        prepared_data = prepare_symbol_execution_data(
            symbol=symbol_data.symbol,
            df=symbol_data.df,
            ranking_mode=ranking_mode,
            min_bars=min_bars,
            lux_analyzer=analyzers.lux_analyzer,
            smc_analyzer=analyzers.smc_analyzer,
        )
        if prepared_data is None:
            if progress:
                _print_progress(
                    processed_symbols=processed_symbols,
                    total_symbols=total_symbols,
                    symbol=symbol_data.symbol,
                    start_time=start_time,
                    symbol_start=symbol_start,
                    status="insufficient_history",
                )
            continue

        symbol_trade_count = 0
        for current_exit_rule in exit_rules:
            symbol_trades = generate_prepared_symbol_trades(
                prepared_data=prepared_data,
                exit_rule=current_exit_rule,
            )
            symbol_trade_count += len(symbol_trades)
            trade_records.extend(
                trade_to_record(
                    trade,
                    exit_rule=current_exit_rule,
                    ranking_mode=ranking_mode,
                )
                for trade in symbol_trades
            )
        if progress:
            _print_progress(
                processed_symbols=processed_symbols,
                total_symbols=total_symbols,
                symbol=symbol_data.symbol,
                start_time=start_time,
                symbol_start=symbol_start,
                status=f"ok trades={symbol_trade_count}",
            )

    trades_df = pd.DataFrame(trade_records)
    summary_df = pd.DataFrame(summarize_trade_records(trade_records))
    comparison_df = pd.DataFrame(
        summarize_execution_rules(trade_records, min_trades=min_trades),
        columns=COMPARISON_COLUMNS,
    )
    symbol_comparison_df = pd.DataFrame(
        summarize_symbol_trade_records(trade_records),
        columns=SYMBOL_COMPARISON_COLUMNS,
    )
    recommendations_df = build_execution_recommendations(
        comparison_df=comparison_df,
        symbol_comparison_df=symbol_comparison_df,
        min_trades=min_trades,
    )
    worst_trades_df = build_worst_trades_report(trades_df)
    write_csv_report(trades_df, output_trades)
    write_csv_report(summary_df, output_summary)
    write_csv_report(comparison_df, output_comparison)
    write_csv_report(symbol_comparison_df, output_symbol_comparison)
    write_csv_report(recommendations_df, output_recommendations)
    write_csv_report(worst_trades_df, output_worst_trades)

    if exit_rule == "all":
        terminal_summary = render_execution_rule_comparison(comparison_df)
    else:
        terminal_summary = render_execution_summary(
            summary_df,
            exit_rule=exit_rule,
            ranking_mode=ranking_mode,
        )
    if terminal_summary:
        print(terminal_summary)
    print(f"\nExported trades: {Path(output_trades)}")
    print(f"Exported summary: {Path(output_summary)}")
    print(f"Exported comparison: {Path(output_comparison)}")
    print(f"Exported symbol comparison: {Path(output_symbol_comparison)}")
    print(f"Exported recommendations: {Path(output_recommendations)}")
    print(f"Exported worst trades: {Path(output_worst_trades)}")
    return trades_df, summary_df


def resolve_exit_rules(exit_rule: str) -> list[str]:
    if exit_rule == "all":
        return list(ALL_EXIT_RULES)
    if exit_rule not in ALL_EXIT_RULES:
        raise ValueError(f"Unsupported exit rule: {exit_rule}")
    return [exit_rule]


def summarize_execution_rules(records: list[dict], min_trades: int = 20) -> list[dict]:
    return rank_execution_rules(summarize_trade_records(records), min_trades=min_trades)


def rank_execution_rules(
    summary_rows: list[dict],
    *,
    min_trades: int = 20,
) -> list[dict]:
    comparison_rows = [
        _with_qualification(row, min_trades=min_trades) for row in summary_rows
    ]
    qualified = [row for row in comparison_rows if row["qualified"]]
    unqualified = [row for row in comparison_rows if not row["qualified"]]

    qualified.sort(key=_comparison_sort_key, reverse=True)
    unqualified.sort(key=_comparison_sort_key, reverse=True)

    for index, row in enumerate(qualified, start=1):
        row["rank"] = index
    for row in unqualified:
        row["rank"] = None

    return qualified + unqualified


def build_execution_recommendations(
    *,
    comparison_df: pd.DataFrame,
    symbol_comparison_df: pd.DataFrame,
    min_trades: int = 20,
) -> pd.DataFrame:
    rows: list[dict] = []
    if not comparison_df.empty:
        for side, group in comparison_df.groupby("side", sort=True):
            rows.append(
                _build_recommendation_row(
                    group=group,
                    scope="global",
                    symbol=None,
                    side=str(side),
                    min_trades=min_trades,
                )
            )

    if not symbol_comparison_df.empty:
        grouped = symbol_comparison_df.groupby(["symbol", "side"], sort=True)
        for (symbol, side), group in grouped:
            rows.append(
                _build_recommendation_row(
                    group=group,
                    scope="symbol",
                    symbol=str(symbol),
                    side=str(side),
                    min_trades=min_trades,
                )
            )

    return pd.DataFrame(rows, columns=RECOMMENDATION_COLUMNS)


def build_worst_trades_report(
    trades_df: pd.DataFrame,
    *,
    limit: int = 50,
) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame(columns=WORST_TRADES_COLUMNS)

    report_frames = [
        _worst_trades_slice(
            trades_df,
            reason="worst_directional_return",
            sort_columns=["directional_return", "mae", "bars_held"],
            ascending=[True, True, False],
            limit=limit,
        ),
        _worst_trades_slice(
            trades_df,
            reason="worst_mae",
            sort_columns=["mae", "directional_return", "bars_held"],
            ascending=[True, True, False],
            limit=limit,
        ),
        _worst_trades_slice(
            trades_df,
            reason="longest_hold",
            sort_columns=["bars_held", "mae", "directional_return"],
            ascending=[False, True, True],
            limit=limit,
        ),
    ]
    report = pd.concat(report_frames, ignore_index=True)
    report = report.drop_duplicates(
        subset=["report_reason", "symbol", "side", "entry_date", "exit_rule"]
    )
    return report.loc[
        :, [column for column in WORST_TRADES_COLUMNS if column in report.columns]
    ]


def generate_symbol_trades(
    *,
    symbol: str,
    df: pd.DataFrame,
    ranking_mode: str,
    exit_rule: str,
    min_bars: int,
    lux_analyzer: StockDataAnalyzer | None = None,
    smc_analyzer: StockDataAnalyzer | None = None,
) -> list[Trade]:
    prepared_data = prepare_symbol_execution_data(
        symbol=symbol,
        df=df,
        ranking_mode=ranking_mode,
        min_bars=min_bars,
        lux_analyzer=lux_analyzer,
        smc_analyzer=smc_analyzer,
    )
    if prepared_data is None:
        return []
    return generate_prepared_symbol_trades(
        prepared_data=prepared_data,
        exit_rule=exit_rule,
    )


def prepare_symbol_execution_data(
    *,
    symbol: str,
    df: pd.DataFrame,
    ranking_mode: str,
    min_bars: int,
    lux_analyzer: StockDataAnalyzer | None = None,
    smc_analyzer: StockDataAnalyzer | None = None,
) -> PreparedSymbolExecutionData | None:
    effective_min_bars = max(min_bars, SCANNER_ROW_MIN_BARS)
    if len(df) < effective_min_bars:
        return None

    lux_analyzer = lux_analyzer or StockDataAnalyzer(signal_model="lux")
    smc_analyzer = smc_analyzer or StockDataAnalyzer(signal_model="smc")
    lux_historical = lux_analyzer.generate_historical_signals(symbol, df)
    smc_historical = smc_analyzer.generate_historical_signals(symbol, df)
    close_column = _require_column(df, "close")
    high_column = _require_column(df, "high")
    low_column = _require_column(df, "low")

    bars: list[ExecutionBar] = []
    start_index = max(effective_min_bars - 1, 0)
    for index in range(start_index, len(df)):
        close_price = float(df.iloc[index][close_column])
        row = build_scanner_row_from_history(
            symbol=symbol,
            close=close_price,
            lux_historical=lux_historical,
            smc_historical=smc_historical,
            index=index,
            ranking_mode=ranking_mode,
        )
        bar_date = pd.Timestamp(df.index[index]).isoformat()
        bars.append(
            ExecutionBar(
                index=index,
                date=bar_date,
                close=close_price,
                row=row,
            )
        )

    return PreparedSymbolExecutionData(
        symbol=symbol,
        df=df,
        bars=bars,
        high_column=high_column,
        low_column=low_column,
    )


def generate_prepared_symbol_trades(
    *,
    prepared_data: PreparedSymbolExecutionData,
    exit_rule: str,
) -> list[Trade]:
    trades: list[Trade] = []
    open_position: OpenPosition | None = None

    for bar in prepared_data.bars:
        exited_this_bar = False

        if open_position is not None and _should_exit(
            row=bar.row,
            side=open_position.side,
            exit_rule=exit_rule,
            bars_held=_bars_held(open_position.entry_index, bar.index),
        ):
            trades.append(
                _close_trade(
                    symbol=prepared_data.symbol,
                    df=prepared_data.df,
                    open_position=open_position,
                    exit_index=bar.index,
                    exit_date=bar.date,
                    exit_price=bar.close,
                    exit_reason=exit_rule,
                    high_column=prepared_data.high_column,
                    low_column=prepared_data.low_column,
                )
            )
            open_position = None
            exited_this_bar = True

        if open_position is None and not exited_this_bar:
            side = _entry_side(bar.row)
            if side is not None:
                open_position = OpenPosition(
                    symbol=prepared_data.symbol,
                    side=side,
                    entry_index=bar.index,
                    entry_date=bar.date,
                    entry_price=bar.close,
                    entry_alignment=str(bar.row["adjusted_alignment"]),
                )

    if open_position is not None:
        final_bar = prepared_data.bars[-1]
        trades.append(
            _close_trade(
                symbol=prepared_data.symbol,
                df=prepared_data.df,
                open_position=open_position,
                exit_index=final_bar.index,
                exit_date=final_bar.date,
                exit_price=final_bar.close,
                exit_reason="end_of_data",
                high_column=prepared_data.high_column,
                low_column=prepared_data.low_column,
            )
        )

    return trades


def render_execution_summary(
    summary_df: pd.DataFrame,
    *,
    exit_rule: str,
    ranking_mode: str,
) -> str:
    if summary_df.empty:
        return "No execution trades generated."

    lines = [
        "EXECUTION BACKTEST",
        "",
        f"Exit rule: {exit_rule}",
        f"Ranking mode: {ranking_mode}",
    ]

    for side in ("bullish", "bearish"):
        side_rows = summary_df[summary_df["side"] == side]
        if side_rows.empty:
            continue

        directional = _aggregate_weighted(side_rows, "avg_directional_return")
        expectancy = _aggregate_weighted(side_rows, "expectancy")
        avg_bars = _aggregate_weighted(side_rows, "avg_bars_held")
        avg_mfe = _aggregate_weighted(side_rows, "avg_mfe")
        avg_mae = _aggregate_weighted(side_rows, "avg_mae")
        win_rate = _aggregate_weighted(side_rows, "win_rate")
        loss_rate = _aggregate_weighted(side_rows, "loss_rate")
        total_trades = int(pd.to_numeric(side_rows["total_trades"]).sum())

        lines.extend(
            [
                "",
                f"{side.upper()} trades",
                (
                    f"trades={total_trades} | win_rate={_format_percent(win_rate)} | "
                    f"loss_rate={_format_percent(loss_rate)}"
                ),
                (
                    "avg_directional_return="
                    f"{_format_signed_percent(directional)} | expectancy="
                    f"{_format_signed_percent(expectancy)}"
                ),
                (
                    f"avg_bars_held={_format_decimal(avg_bars)} | "
                    f"avg_mfe={_format_signed_percent(avg_mfe)} | "
                    f"avg_mae={_format_signed_percent(avg_mae)}"
                ),
            ]
        )

    return "\n".join(lines)


def render_execution_rule_comparison(
    comparison_df: pd.DataFrame,
    limit: int = 10,
) -> str:
    if comparison_df.empty:
        return "No execution trades generated."

    lines = ["BEST EXECUTION RULES"]
    qualified = comparison_df[comparison_df["qualified"] == True].head(limit)  # noqa: E712
    if qualified.empty:
        lines.extend(["", "No qualified execution rules."])
    else:
        for _, row in qualified.iterrows():
            lines.extend(["", _render_comparison_row(row, ranked=True)])

    unqualified = comparison_df[comparison_df["qualified"] == False].head(limit)  # noqa: E712
    lines.extend(["", "UNQUALIFIED RULES"])
    if unqualified.empty:
        lines.extend(["", "None"])
    else:
        for _, row in unqualified.iterrows():
            lines.extend(["", _render_comparison_row(row, ranked=False)])

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Market scanner execution backtest")
    parser.add_argument("--universe-file", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument(
        "--ranking-mode",
        choices=["snapshot", "recent-event"],
        default="recent-event",
        help="Scanner row basis used to drive entries and exits.",
    )
    parser.add_argument(
        "--exit-rule",
        choices=list(EXIT_RULE_CHOICES),
        required=True,
        help=(
            "Exit rule experiment to simulate. Use 'all' to compare every "
            "supported rule while preparing scanner rows once per symbol."
        ),
    )
    parser.add_argument("--min-bars", type=int, default=DEFAULT_MIN_BARS)
    parser.add_argument(
        "--output-trades",
        default=f"{DEFAULT_REPORTS_DIR}/execution_trades.csv",
    )
    parser.add_argument(
        "--output-summary",
        default=f"{DEFAULT_REPORTS_DIR}/execution_summary.csv",
    )
    parser.add_argument(
        "--output-comparison",
        default=f"{DEFAULT_REPORTS_DIR}/execution_rule_comparison.csv",
    )
    parser.add_argument(
        "--output-symbol-comparison",
        default=f"{DEFAULT_REPORTS_DIR}/execution_symbol_comparison.csv",
    )
    parser.add_argument(
        "--output-recommendations",
        default=f"{DEFAULT_REPORTS_DIR}/execution_recommended_rules.csv",
    )
    parser.add_argument(
        "--output-worst-trades",
        default=f"{DEFAULT_REPORTS_DIR}/execution_worst_trades.csv",
    )
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print per-symbol elapsed time and ETA during execution.",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated symbol filter",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    backtest_execution_universe(
        universe_file=args.universe_file,
        data_dir=args.data_dir,
        ranking_mode=args.ranking_mode,
        exit_rule=args.exit_rule,
        min_bars=args.min_bars,
        output_trades=args.output_trades,
        output_summary=args.output_summary,
        output_comparison=args.output_comparison,
        output_symbol_comparison=args.output_symbol_comparison,
        output_recommendations=args.output_recommendations,
        output_worst_trades=args.output_worst_trades,
        min_trades=args.min_trades,
        symbols=_parse_symbols(args.symbols),
        progress=args.progress,
    )
    return 0


def _entry_side(row: dict) -> TradeSide | None:
    if (
        row.get("action_bucket") == "candidate"
        and row.get("adjusted_alignment") == "bullish_aligned"
    ):
        return "bullish"
    if (
        row.get("action_bucket") == "candidate"
        and row.get("adjusted_alignment") == "bearish_aligned"
    ):
        return "bearish"
    return None


def _should_exit(
    *,
    row: dict,
    side: TradeSide,
    exit_rule: str,
    bars_held: int,
) -> bool:
    if exit_rule == "alignment_break":
        return exit_on_alignment_break(row, side)
    if exit_rule == "bucket_downgrade":
        return exit_on_bucket_downgrade(row)
    if exit_rule == "late_state":
        return exit_on_late_state(row)
    if exit_rule == "opposite_signal":
        return exit_on_opposite_signal(row, side)
    if exit_rule == "bars_5":
        return exit_after_n_bars(bars_held, 5)
    if exit_rule == "bars_10":
        return exit_after_n_bars(bars_held, 10)
    if exit_rule == "bars_20":
        return exit_after_n_bars(bars_held, 20)
    raise ValueError(f"Unsupported exit rule: {exit_rule}")


def _close_trade(
    *,
    symbol: str,
    df: pd.DataFrame,
    open_position: OpenPosition,
    exit_index: int,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
    high_column: str,
    low_column: str,
) -> Trade:
    window = df.iloc[open_position.entry_index : exit_index + 1]
    mfe, mae = compute_trade_excursions(
        window=window,
        entry_price=open_position.entry_price,
        side=open_position.side,
        high_column=high_column,
        low_column=low_column,
    )
    return build_trade(
        symbol=symbol,
        side=open_position.side,
        entry_date=open_position.entry_date,
        entry_price=open_position.entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        bars_held=_bars_held(open_position.entry_index, exit_index),
        entry_alignment=open_position.entry_alignment,
        exit_reason=exit_reason,
        mfe=mfe,
        mae=mae,
    )


def _bars_held(entry_index: int, current_index: int) -> int:
    return (current_index - entry_index) + 1


def _require_column(df: pd.DataFrame, name: str) -> str:
    lowered = {str(column).lower(): str(column) for column in df.columns}
    if name not in lowered:
        raise ValueError(f"DataFrame must contain a '{name}' column")
    return lowered[name]


def _parse_symbols(raw_symbols: str | None) -> list[str] | None:
    if raw_symbols is None:
        return None
    symbols = [
        symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()
    ]
    return symbols or None


def _worst_trades_slice(
    trades_df: pd.DataFrame,
    *,
    reason: str,
    sort_columns: list[str],
    ascending: list[bool],
    limit: int,
) -> pd.DataFrame:
    available_sort_columns = [
        column for column in sort_columns if column in trades_df.columns
    ]
    if not available_sort_columns:
        return pd.DataFrame(columns=WORST_TRADES_COLUMNS)

    sort_directions = ascending[: len(available_sort_columns)]
    result = trades_df.sort_values(
        available_sort_columns,
        ascending=sort_directions,
        na_position="last",
    ).head(limit)
    result = result.copy()
    result.insert(0, "report_reason", reason)
    return result


def _print_progress(
    *,
    processed_symbols: int,
    total_symbols: int,
    symbol: str,
    start_time: float,
    symbol_start: float,
    status: str,
) -> None:
    now = perf_counter()
    elapsed = now - start_time
    symbol_elapsed = now - symbol_start
    eta = _estimate_eta(
        processed_symbols=processed_symbols,
        total_symbols=total_symbols,
        elapsed=elapsed,
    )
    print(
        "[execution progress] "
        f"{processed_symbols}/{total_symbols} {symbol} "
        f"status={status} "
        f"symbol_elapsed={_format_duration(symbol_elapsed)} "
        f"elapsed={_format_duration(elapsed)} "
        f"eta={_format_duration(eta)}",
        flush=True,
    )


def _estimate_eta(
    *,
    processed_symbols: int,
    total_symbols: int,
    elapsed: float,
) -> float | None:
    if processed_symbols <= 0 or total_symbols <= processed_symbols:
        return 0.0
    average_per_symbol = elapsed / processed_symbols
    return average_per_symbol * (total_symbols - processed_symbols)


def _format_duration(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return "n/a"
    seconds = max(0, int(round(seconds)))
    minutes, second = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minute:02d}m{second:02d}s"
    if minutes:
        return f"{minutes}m{second:02d}s"
    return f"{second}s"


def _with_qualification(row: dict, *, min_trades: int) -> dict:
    comparison_row = {column: row.get(column) for column in COMPARISON_COLUMNS}
    reasons = _qualification_reasons(row, min_trades=min_trades)
    comparison_row["qualified"] = not reasons
    comparison_row["qualification_reason"] = (
        "; ".join(reasons) if reasons else "qualified"
    )
    comparison_row["rank"] = None
    return comparison_row


def _qualification_reasons(row: dict, *, min_trades: int) -> list[str]:
    total_trades = int(row.get("total_trades") or 0)
    expectancy = row.get("expectancy")
    avg_directional_return = row.get("avg_directional_return")
    reasons: list[str] = []

    if total_trades < min_trades:
        reasons.append("not enough trades")
    if expectancy is None or pd.isna(expectancy) or expectancy <= 0:
        reasons.append("negative expectancy")
    if (
        avg_directional_return is None
        or pd.isna(avg_directional_return)
        or avg_directional_return <= 0
    ):
        reasons.append("negative avg directional return")

    return reasons


def _build_recommendation_row(
    *,
    group: pd.DataFrame,
    scope: str,
    symbol: str | None,
    side: str,
    min_trades: int,
) -> dict:
    candidates = []
    for record in group.to_dict("records"):
        reasons = _qualification_reasons(record, min_trades=min_trades)
        candidate = dict(record)
        candidate["qualified"] = not reasons
        candidate["qualification_reason"] = (
            "; ".join(reasons) if reasons else "qualified"
        )
        candidates.append(candidate)

    qualified = [candidate for candidate in candidates if candidate["qualified"]]
    ranked_candidates = qualified if qualified else candidates
    ranked_candidates.sort(key=_comparison_sort_key, reverse=True)
    best = ranked_candidates[0]

    return {
        "scope": scope,
        "symbol": symbol,
        "side": side,
        "recommended_exit_rule": best.get("exit_rule"),
        "qualified": best.get("qualified"),
        "qualification_reason": best.get("qualification_reason"),
        "ranking_mode": best.get("ranking_mode"),
        "entry_alignment": best.get("entry_alignment"),
        "total_trades": best.get("total_trades"),
        "win_rate": best.get("win_rate"),
        "loss_rate": best.get("loss_rate"),
        "avg_directional_return": best.get("avg_directional_return"),
        "median_directional_return": best.get("median_directional_return"),
        "expectancy": best.get("expectancy"),
        "profit_factor": best.get("profit_factor"),
        "avg_mfe": best.get("avg_mfe"),
        "avg_mae": best.get("avg_mae"),
        "avg_bars_held": best.get("avg_bars_held"),
        "best_trade": best.get("best_trade"),
        "worst_trade": best.get("worst_trade"),
    }


def _comparison_sort_key(row: dict) -> tuple:
    profit_factor = row.get("profit_factor")
    if profit_factor is None or pd.isna(profit_factor):
        profit_factor_sort = float("-inf")
    else:
        profit_factor_sort = float(profit_factor)
    return (
        _numeric_or_negative_infinity(row.get("expectancy")),
        profit_factor_sort,
        _numeric_or_negative_infinity(row.get("avg_directional_return")),
        _numeric_or_negative_infinity(row.get("avg_mae")),
        _numeric_or_negative_infinity(row.get("total_trades")),
    )


def _numeric_or_negative_infinity(value: object) -> float:
    if value is None or pd.isna(value):
        return float("-inf")
    return float(value)


def _render_comparison_row(row: pd.Series, *, ranked: bool) -> str:
    heading_parts = []
    if ranked:
        heading_parts.append(f"{int(row['rank'])})")
    heading_parts.extend(
        [
            str(row["exit_rule"]),
            str(row["side"]),
            str(row["ranking_mode"]),
            str(row["entry_alignment"]),
        ]
    )
    if ranked:
        heading = " ".join([heading_parts[0], " | ".join(heading_parts[1:])])
    else:
        heading = " | ".join(heading_parts)

    lines = [
        heading,
        (
            f"trades={int(row['total_trades'])} | "
            f"win={_format_percent(row.get('win_rate'))} | "
            f"loss={_format_percent(row.get('loss_rate'))}"
        ),
        (
            f"expectancy={_format_signed_percent(row.get('expectancy'))} | "
            "avg_dir_return="
            f"{_format_signed_percent(row.get('avg_directional_return'))} | "
            f"profit_factor={_format_decimal(row.get('profit_factor'))}"
        ),
        (
            f"avg_mfe={_format_signed_percent(row.get('avg_mfe'))} | "
            f"avg_mae={_format_signed_percent(row.get('avg_mae'))} | "
            f"avg_hold={_format_decimal(row.get('avg_bars_held'))} bars"
        ),
    ]
    if not ranked:
        lines.append(f"reason={row.get('qualification_reason')}")
    return "\n".join(lines)


def _aggregate_weighted(df: pd.DataFrame, value_column: str) -> float | None:
    values = pd.to_numeric(df[value_column], errors="coerce")
    weights = pd.to_numeric(df["total_trades"], errors="coerce")
    valid = values.notna() & weights.notna()
    if not valid.any():
        return None
    total_weight = float(weights[valid].sum())
    if total_weight == 0:
        return None
    return float((values[valid] * weights[valid]).sum() / total_weight)


def _format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def _format_signed_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:+.1%}"


def _format_decimal(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1f}"


if __name__ == "__main__":
    raise SystemExit(main())

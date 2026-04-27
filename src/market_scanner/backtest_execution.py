import argparse
from dataclasses import dataclass
from pathlib import Path

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
    trade_to_record,
)
from stock_analyzer.analyzer import StockDataAnalyzer

DEFAULT_MIN_BARS = 120
SCANNER_ROW_MIN_BARS = MIN_HISTORY_ROWS
DEFAULT_REPORTS_DIR = "reports/market_scanner"
EXIT_RULE_CHOICES = (
    "alignment_break",
    "bucket_downgrade",
    "late_state",
    "opposite_signal",
    "bars_5",
    "bars_10",
    "bars_20",
)


@dataclass
class OpenPosition:
    symbol: str
    side: TradeSide
    entry_index: int
    entry_date: str
    entry_price: float
    entry_alignment: str


def backtest_execution_universe(
    *,
    universe_file: str | Path,
    data_dir: str | Path,
    ranking_mode: str,
    exit_rule: str,
    min_bars: int = DEFAULT_MIN_BARS,
    output_trades: str | Path = f"{DEFAULT_REPORTS_DIR}/execution_trades.csv",
    output_summary: str | Path = f"{DEFAULT_REPORTS_DIR}/execution_summary.csv",
    symbols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    universe = load_selected_universe(universe_file, symbols=symbols)
    analyzers = create_analyzers(StockDataAnalyzer)
    trade_records: list[dict] = []

    def _transform_df(df: pd.DataFrame) -> pd.DataFrame:
        return prepare_backtest_df(df=df.sort_index())

    for symbol_data in iter_symbol_data(universe, data_dir, transform_df=_transform_df):
        if symbol_data.load_error is not None or symbol_data.df is None:
            continue

        symbol_trades = generate_symbol_trades(
            symbol=symbol_data.symbol,
            df=symbol_data.df,
            ranking_mode=ranking_mode,
            exit_rule=exit_rule,
            min_bars=min_bars,
            lux_analyzer=analyzers.lux_analyzer,
            smc_analyzer=analyzers.smc_analyzer,
        )
        trade_records.extend(
            trade_to_record(
                trade,
                exit_rule=exit_rule,
                ranking_mode=ranking_mode,
            )
            for trade in symbol_trades
        )

    trades_df = pd.DataFrame(trade_records)
    summary_df = pd.DataFrame(summarize_trade_records(trade_records))
    write_csv_report(trades_df, output_trades)
    write_csv_report(summary_df, output_summary)

    terminal_summary = render_execution_summary(
        summary_df,
        exit_rule=exit_rule,
        ranking_mode=ranking_mode,
    )
    if terminal_summary:
        print(terminal_summary)
    print(f"\nExported trades: {Path(output_trades)}")
    print(f"Exported summary: {Path(output_summary)}")
    return trades_df, summary_df


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
    effective_min_bars = max(min_bars, SCANNER_ROW_MIN_BARS)
    if len(df) < effective_min_bars:
        return []

    lux_analyzer = lux_analyzer or StockDataAnalyzer(signal_model="lux")
    smc_analyzer = smc_analyzer or StockDataAnalyzer(signal_model="smc")
    lux_historical = lux_analyzer.generate_historical_signals(symbol, df)
    smc_historical = smc_analyzer.generate_historical_signals(symbol, df)
    close_column = _require_column(df, "close")
    high_column = _require_column(df, "high")
    low_column = _require_column(df, "low")

    trades: list[Trade] = []
    open_position: OpenPosition | None = None
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
        exited_this_bar = False

        if open_position is not None and _should_exit(
            row=row,
            side=open_position.side,
            exit_rule=exit_rule,
            bars_held=_bars_held(open_position.entry_index, index),
        ):
            trades.append(
                _close_trade(
                    symbol=symbol,
                    df=df,
                    open_position=open_position,
                    exit_index=index,
                    exit_date=bar_date,
                    exit_price=close_price,
                    exit_reason=exit_rule,
                    high_column=high_column,
                    low_column=low_column,
                )
            )
            open_position = None
            exited_this_bar = True

        if open_position is None and not exited_this_bar:
            side = _entry_side(row)
            if side is not None:
                open_position = OpenPosition(
                    symbol=symbol,
                    side=side,
                    entry_index=index,
                    entry_date=bar_date,
                    entry_price=close_price,
                    entry_alignment=str(row["adjusted_alignment"]),
                )

    if open_position is not None:
        final_index = len(df) - 1
        final_close = float(df.iloc[final_index][close_column])
        final_date = pd.Timestamp(df.index[final_index]).isoformat()
        trades.append(
            _close_trade(
                symbol=symbol,
                df=df,
                open_position=open_position,
                exit_index=final_index,
                exit_date=final_date,
                exit_price=final_close,
                exit_reason="end_of_data",
                high_column=high_column,
                low_column=low_column,
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
        help="Exit rule experiment to simulate.",
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
        symbols=_parse_symbols(args.symbols),
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

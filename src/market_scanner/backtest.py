import argparse
from pathlib import Path

import pandas as pd

from market_scanner.eligibility import MIN_HISTORY_ROWS
from market_scanner.pipeline import (
    create_analyzers,
    iter_symbol_data,
    load_selected_universe,
)
from market_scanner.report_writer import write_csv_report
from market_scanner.scanner_row import build_scanner_row_from_history
from stock_analyzer.analyzer import StockDataAnalyzer

DEFAULT_HORIZONS = (3, 5, 10, 20)
DEFAULT_MIN_BARS = 120
DEFAULT_WIN_THRESHOLD = 0.01
SCANNER_ROW_MIN_BARS = MIN_HISTORY_ROWS
DEFAULT_REPORTS_DIR = "reports/market_scanner"
DETAILED_SUMMARY_GROUP_COLUMNS = [
    "signal_side",
    "action_bucket",
    "market_state",
    "adjusted_alignment",
    "lux_strength",
    "ranking_mode",
]
DECISION_SUMMARY_GROUP_COLUMNS = [
    "signal_side",
    "action_bucket",
    "market_state",
    "lux_strength",
    "ranking_mode",
]


def infer_signal_side(adjusted_alignment: str | None) -> str:
    if str(adjusted_alignment or "").startswith("bullish"):
        return "bullish"
    if str(adjusted_alignment or "").startswith("bearish"):
        return "bearish"
    return "neutral"


def infer_direction(adjusted_alignment: str | None) -> str:
    return infer_signal_side(adjusted_alignment)


def compute_forward_metrics(
    df: pd.DataFrame,
    index: int,
    horizons: list[int],
    direction: str,
    win_threshold: float,
) -> dict:
    close_column = _require_column(df, "close")
    high_column = _require_column(df, "high")
    low_column = _require_column(df, "low")
    entry_close = float(df.iloc[index][close_column])
    metrics: dict[str, float | bool | None] = {"entry_close": entry_close}

    for horizon in horizons:
        future_close = float(df.iloc[index + horizon][close_column])
        raw_return = (future_close / entry_close) - 1.0
        directional_return = _directional_return(raw_return, direction)
        window = df.iloc[index : index + horizon + 1]
        mfe, mae = _compute_excursions(
            window=window,
            entry_close=entry_close,
            direction=direction,
            high_column=high_column,
            low_column=low_column,
        )
        win = _classify_win(directional_return, win_threshold)

        metrics[f"return_{horizon}"] = raw_return
        metrics[f"directional_return_{horizon}"] = directional_return
        metrics[f"mfe_{horizon}"] = mfe
        metrics[f"mae_{horizon}"] = mae
        metrics[f"win_{horizon}"] = win

    return metrics


def build_backtest_event(
    *,
    symbol: str,
    date: pd.Timestamp,
    row: dict,
    df: pd.DataFrame,
    index: int,
    horizons: list[int],
    win_threshold: float,
) -> dict:
    signal_side = infer_signal_side(row.get("adjusted_alignment"))
    event = {
        "symbol": symbol,
        "date": pd.Timestamp(date).isoformat(),
        "ranking_mode": row.get("ranking_mode"),
        "market_state": row.get("market_state"),
        "adjusted_alignment": row.get("adjusted_alignment"),
        "action_bucket": row.get("action_bucket"),
        "consistency_score": row.get("consistency_score"),
        "alignment": row.get("alignment"),
        "lux_role": row.get("lux_role"),
        "lux_signal": row.get("lux_signal"),
        "lux_options_hint": row.get("lux_options_hint"),
        "lux_context": row.get("lux_context"),
        "lux_trend": row.get("lux_trend"),
        "lux_strength": row.get("lux_strength"),
        "lux_last_event": row.get("lux_last_event"),
        "lux_days_since_last_event": row.get("lux_days_since_last_event"),
        "lux_active_event": row.get("lux_active_event"),
        "lux_days_since_active_event": row.get("lux_days_since_active_event"),
        "smc_role": row.get("smc_role"),
        "smc_signal": row.get("smc_signal"),
        "smc_options_hint": row.get("smc_options_hint"),
        "smc_context": row.get("smc_context"),
        "smc_bias": row.get("smc_bias"),
        "smc_range_position_pct": row.get("smc_range_position_pct"),
        "smc_rsi": row.get("smc_rsi"),
        "signal_side": signal_side,
        "direction": signal_side,
    }
    event.update(
        compute_forward_metrics(
            df=df,
            index=index,
            horizons=horizons,
            direction=signal_side,
            win_threshold=win_threshold,
        )
    )
    return event


def generate_symbol_events(
    *,
    symbol: str,
    df: pd.DataFrame,
    ranking_modes: list[str],
    min_bars: int,
    horizons: list[int],
    win_threshold: float,
    lux_analyzer: StockDataAnalyzer | None = None,
    smc_analyzer: StockDataAnalyzer | None = None,
) -> list[dict]:
    effective_min_bars = max(min_bars, SCANNER_ROW_MIN_BARS)
    max_horizon = max(horizons)
    if len(df) < effective_min_bars + max_horizon:
        return []

    events: list[dict] = []
    start_index = max(effective_min_bars - 1, 0)
    lux_analyzer = lux_analyzer or StockDataAnalyzer(signal_model="lux")
    smc_analyzer = smc_analyzer or StockDataAnalyzer(signal_model="smc")
    lux_historical = lux_analyzer.generate_historical_signals(symbol, df)
    smc_historical = smc_analyzer.generate_historical_signals(symbol, df)
    close_column = _require_column(df, "close")

    for i in range(start_index, len(df) - max_horizon):
        entry_close = float(df.iloc[i][close_column])
        for ranking_mode in ranking_modes:
            row = build_scanner_row_from_history(
                symbol=symbol,
                close=entry_close,
                lux_historical=lux_historical,
                smc_historical=smc_historical,
                index=i,
                ranking_mode=ranking_mode,
            )
            events.append(
                build_backtest_event(
                    symbol=symbol,
                    date=pd.Timestamp(df.index[i]),
                    row=row,
                    df=df,
                    index=i,
                    horizons=horizons,
                    win_threshold=win_threshold,
                )
            )

    return events


def summarize_events(events: list[dict], horizons: list[int]) -> list[dict]:
    return summarize_detailed_events(events, horizons)


def summarize_detailed_events(events: list[dict], horizons: list[int]) -> list[dict]:
    return _summarize_events(events, horizons, DETAILED_SUMMARY_GROUP_COLUMNS)


def summarize_decision_events(events: list[dict], horizons: list[int]) -> list[dict]:
    return _summarize_events(events, horizons, DECISION_SUMMARY_GROUP_COLUMNS)


def backtest_universe(
    *,
    universe_file: str | Path,
    data_dir: str | Path,
    ranking_mode: str,
    min_bars: int = DEFAULT_MIN_BARS,
    horizons: list[int] | None = None,
    win_threshold: float = DEFAULT_WIN_THRESHOLD,
    output_events: str | Path = f"{DEFAULT_REPORTS_DIR}/backtest_events.csv",
    output_detailed_summary: str | Path = (
        f"{DEFAULT_REPORTS_DIR}/backtest_detailed_summary.csv"
    ),
    output_decision_summary: str | Path = (
        f"{DEFAULT_REPORTS_DIR}/backtest_decision_summary.csv"
    ),
    symbols: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    max_bars: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    horizons = horizons or list(DEFAULT_HORIZONS)
    ranking_modes = _resolve_ranking_modes(ranking_mode)
    universe = load_selected_universe(universe_file, symbols=symbols)
    analyzers = create_analyzers(StockDataAnalyzer)
    events: list[dict] = []

    def _transform_df(df: pd.DataFrame) -> pd.DataFrame:
        return prepare_backtest_df(
            df=df.sort_index(),
            start_date=start_date,
            end_date=end_date,
            max_bars=max_bars,
        )

    for symbol_data in iter_symbol_data(universe, data_dir, transform_df=_transform_df):
        if symbol_data.load_error is not None or symbol_data.df is None:
            continue

        symbol = symbol_data.symbol
        df = symbol_data.df

        events.extend(
            generate_symbol_events(
                symbol=symbol,
                df=df,
                ranking_modes=ranking_modes,
                min_bars=min_bars,
                horizons=horizons,
                win_threshold=win_threshold,
                lux_analyzer=analyzers.lux_analyzer,
                smc_analyzer=analyzers.smc_analyzer,
            )
        )

    events_df = pd.DataFrame(events)
    detailed_summary_df = pd.DataFrame(summarize_detailed_events(events, horizons))
    decision_summary_df = pd.DataFrame(summarize_decision_events(events, horizons))
    write_csv_report(events_df, output_events)
    write_csv_report(detailed_summary_df, output_detailed_summary)
    write_csv_report(decision_summary_df, output_decision_summary)

    terminal_summary = render_decision_summary(decision_summary_df)
    if terminal_summary:
        print(terminal_summary)
    print(f"\nExported events: {Path(output_events)}")
    print(f"Exported detailed summary: {Path(output_detailed_summary)}")
    print(f"Exported decision summary: {Path(output_decision_summary)}")
    return events_df, detailed_summary_df, decision_summary_df


def render_backtest_summary(summary_df: pd.DataFrame, limit: int = 12) -> str:
    return render_decision_summary(summary_df, limit=limit)


def render_decision_summary(
    decision_summary_df: pd.DataFrame,
    *,
    limit: int = 12,
    include_neutral: bool = False,
) -> str:
    if decision_summary_df.empty:
        return "No backtest events generated."

    summary_df = decision_summary_df.copy()
    if not include_neutral:
        summary_df = summary_df[summary_df["signal_side"] != "neutral"]
    if summary_df.empty:
        return "No directional backtest events generated."

    ordered = _ordered_summary(summary_df).head(limit)
    lines = []
    for row in ordered.itertuples(index=False):
        signal_side = str(row.signal_side).upper()
        lines.append(
            f"{signal_side} signal | {row.action_bucket} | {row.market_state} | "
            f"{row.lux_strength} | h={row.horizon}"
        )
        success = (
            f"{row.success_rate * 100:.1f}%" if pd.notna(row.success_rate) else "n/a"
        )
        failure = (
            f"{row.failure_rate * 100:.1f}%" if pd.notna(row.failure_rate) else "n/a"
        )
        avg_directional_return = (
            f"{row.avg_directional_return:+.1%}"
            if pd.notna(row.avg_directional_return)
            else "n/a"
        )
        expectancy = f"{row.expectancy:+.1%}" if pd.notna(row.expectancy) else "n/a"
        lines.append(
            f"signals={row.signals} | success={success} | failure={failure} | "
            f"avg_directional_return={avg_directional_return} | expectancy={expectancy}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Market scanner signal-quality backtest")
    parser.add_argument("--universe-file", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument(
        "--ranking-mode",
        choices=["snapshot", "recent-event", "both"],
        default="recent-event",
    )
    parser.add_argument("--min-bars", type=int, default=DEFAULT_MIN_BARS)
    parser.add_argument("--horizons", default="3,5,10,20")
    parser.add_argument("--win-threshold", type=float, default=DEFAULT_WIN_THRESHOLD)
    parser.add_argument(
        "--output-events",
        default=f"{DEFAULT_REPORTS_DIR}/backtest_events.csv",
    )
    parser.add_argument(
        "--output-summary",
        default=None,
        help="Deprecated alias for --output-detailed-summary",
    )
    parser.add_argument(
        "--output-detailed-summary",
        default=f"{DEFAULT_REPORTS_DIR}/backtest_detailed_summary.csv",
    )
    parser.add_argument(
        "--output-decision-summary",
        default=f"{DEFAULT_REPORTS_DIR}/backtest_decision_summary.csv",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="Comma-separated symbol filter",
    )
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-bars", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    detailed_summary_path = args.output_summary or args.output_detailed_summary
    backtest_universe(
        universe_file=args.universe_file,
        data_dir=args.data_dir,
        ranking_mode=args.ranking_mode,
        min_bars=args.min_bars,
        horizons=_parse_horizons(args.horizons),
        win_threshold=args.win_threshold,
        output_events=args.output_events,
        output_detailed_summary=detailed_summary_path,
        output_decision_summary=args.output_decision_summary,
        symbols=_parse_symbols(args.symbols),
        start_date=args.start_date,
        end_date=args.end_date,
        max_bars=args.max_bars,
    )
    return 0


def prepare_backtest_df(
    *,
    df: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
    max_bars: int | None = None,
) -> pd.DataFrame:
    filtered = df.sort_index()
    if start_date is not None:
        filtered = filtered[filtered.index >= pd.Timestamp(start_date, tz="UTC")]
    if end_date is not None:
        filtered = filtered[filtered.index <= pd.Timestamp(end_date, tz="UTC")]
    if max_bars is not None:
        filtered = filtered.tail(max_bars)
    return filtered.copy()


def _summarize_events(
    events: list[dict],
    horizons: list[int],
    group_columns: list[str],
) -> list[dict]:
    if not events:
        return []

    events_df = pd.DataFrame(events)
    rows: list[dict] = []

    for horizon in horizons:
        metric_df = events_df.copy()
        metric_df["horizon"] = horizon
        metric_df["return"] = pd.to_numeric(
            metric_df[f"return_{horizon}"], errors="coerce"
        )
        metric_df["directional_return"] = pd.to_numeric(
            metric_df[f"directional_return_{horizon}"], errors="coerce"
        )
        metric_df["mfe"] = pd.to_numeric(metric_df[f"mfe_{horizon}"], errors="coerce")
        metric_df["mae"] = pd.to_numeric(metric_df[f"mae_{horizon}"], errors="coerce")
        metric_df["win"] = metric_df[f"win_{horizon}"]

        grouped = metric_df.groupby(group_columns, dropna=False, sort=False)
        for group_values, group in grouped:
            rows.append(_build_summary_row(group_columns, group_values, group, horizon))

    return rows


def _build_summary_row(
    group_columns: list[str],
    group_values: tuple,
    group: pd.DataFrame,
    horizon: int,
) -> dict:
    directional = group["directional_return"].dropna()
    wins = directional[directional > 0]
    losses = directional[directional < 0]
    directional_results = group["win"].dropna()
    success_rate = (
        float(directional_results.astype(float).mean())
        if not directional_results.empty
        else None
    )
    failure_rate = 1.0 - success_rate if success_rate is not None else None
    avg_win = float(wins.mean()) if not wins.empty else None
    avg_loss = float(abs(losses.mean())) if not losses.empty else None
    expectancy = None
    if success_rate is not None and avg_win is not None and avg_loss is not None:
        expectancy = (success_rate * avg_win) - ((1.0 - success_rate) * avg_loss)

    row = dict(zip(group_columns, group_values, strict=True))
    row["group_key"] = " | ".join(str(row[column]) for column in group_columns)
    row["horizon"] = horizon
    row["signals"] = int(len(group))
    row["count"] = row["signals"]
    row["success_rate"] = success_rate
    row["failure_rate"] = failure_rate
    row["win_rate"] = success_rate
    row["avg_return"] = float(group["return"].mean())
    row["avg_directional_return"] = (
        float(directional.mean()) if not directional.empty else None
    )
    row["median_return"] = float(group["return"].median())
    row["avg_mfe"] = (
        float(group["mfe"].dropna().mean()) if group["mfe"].notna().any() else None
    )
    row["avg_mae"] = (
        float(group["mae"].dropna().mean()) if group["mae"].notna().any() else None
    )
    row["avg_win"] = avg_win
    row["avg_loss"] = avg_loss
    row["expectancy"] = expectancy
    return row


def _ordered_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    horizon_priority = {5: 0, 10: 1, 20: 2, 3: 3}
    action_priority = {"candidate": 0, "watchlist": 1, "needs_review": 2, "avoid": 3}
    state_priority = {
        "early_trend": 0,
        "pullback": 1,
        "extended": 2,
        "range": 3,
        "unknown": 4,
        "exhaustion": 5,
    }
    strength_priority = {"STRONG": 0, "NORMAL": 1}
    signal_priority = {"bullish": 0, "bearish": 1, "neutral": 2}

    return summary_df.assign(
        _signal_rank=summary_df["signal_side"].map(signal_priority).fillna(999),
        _action_rank=summary_df["action_bucket"].map(action_priority).fillna(999),
        _strength_rank=summary_df["lux_strength"].map(strength_priority).fillna(999),
        _state_rank=summary_df["market_state"].map(state_priority).fillna(999),
        _horizon_rank=summary_df["horizon"].map(horizon_priority).fillna(999),
    ).sort_values(
        by=[
            "_signal_rank",
            "_action_rank",
            "_strength_rank",
            "_state_rank",
            "_horizon_rank",
            "signals",
        ],
        ascending=[True, True, True, True, True, False],
    )


def _compute_excursions(
    *,
    window: pd.DataFrame,
    entry_close: float,
    direction: str,
    high_column: str,
    low_column: str,
) -> tuple[float | None, float | None]:
    if direction == "bullish":
        mfe = (float(window[high_column].max()) / entry_close) - 1.0
        mae = (float(window[low_column].min()) / entry_close) - 1.0
        return mfe, mae
    if direction == "bearish":
        mfe = 1.0 - (float(window[low_column].min()) / entry_close)
        mae = 1.0 - (float(window[high_column].max()) / entry_close)
        return mfe, mae
    return None, None


def _classify_win(
    directional_return: float | None, win_threshold: float
) -> bool | None:
    if directional_return is None:
        return None
    return directional_return > win_threshold


def _directional_return(raw_return: float, direction: str) -> float | None:
    if direction == "bullish":
        return raw_return
    if direction == "bearish":
        return -raw_return
    return None


def _parse_horizons(raw_horizons: str) -> list[int]:
    return [int(part.strip()) for part in raw_horizons.split(",") if part.strip()]


def _parse_symbols(raw_symbols: str | None) -> list[str] | None:
    if raw_symbols is None:
        return None
    symbols = [
        symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()
    ]
    return symbols or None


def _require_column(df: pd.DataFrame, name: str) -> str:
    lowered = {str(column).lower(): str(column) for column in df.columns}
    if name not in lowered:
        raise ValueError(f"DataFrame must contain a '{name}' column")
    return lowered[name]


def _resolve_ranking_modes(ranking_mode: str) -> list[str]:
    if ranking_mode == "both":
        return ["snapshot", "recent-event"]
    return [ranking_mode]


if __name__ == "__main__":
    raise SystemExit(main())

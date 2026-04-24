import argparse
from pathlib import Path

import pandas as pd

from options_tech_scanner.eligibility import load_symbol_csv
from options_tech_scanner.report_writer import write_csv_report
from options_tech_scanner.scanner_row import build_scanner_row
from options_tech_scanner.universe_loader import load_universe
from stock_analyzer.analyzer import StockDataAnalyzer

DEFAULT_HORIZONS = (3, 5, 10, 20)
DEFAULT_MIN_BARS = 120
DEFAULT_WIN_THRESHOLD = 0.01
SUMMARY_GROUP_COLUMNS = [
    "action_bucket",
    "market_state",
    "adjusted_alignment",
    "lux_strength",
    "ranking_mode",
]


def infer_direction(adjusted_alignment: str | None) -> str:
    if str(adjusted_alignment or "").startswith("bullish"):
        return "bullish"
    if str(adjusted_alignment or "").startswith("bearish"):
        return "bearish"
    return "neutral"


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
    direction = infer_direction(row.get("adjusted_alignment"))
    event = {
        "symbol": symbol,
        "date": pd.Timestamp(date).isoformat(),
        "ranking_mode": row.get("ranking_mode"),
        "market_state": row.get("market_state"),
        "adjusted_alignment": row.get("adjusted_alignment"),
        "action_bucket": row.get("action_bucket"),
        "consistency_score": row.get("consistency_score"),
        "alignment": row.get("alignment"),
        "lux_signal": row.get("lux_signal"),
        "lux_options_hint": row.get("lux_options_hint"),
        "lux_context": row.get("lux_context"),
        "lux_trend": row.get("lux_trend"),
        "lux_strength": row.get("lux_strength"),
        "lux_last_event": row.get("lux_last_event"),
        "lux_days_since_last_event": row.get("lux_days_since_last_event"),
        "lux_active_event": row.get("lux_active_event"),
        "lux_days_since_active_event": row.get("lux_days_since_active_event"),
        "smc_signal": row.get("smc_signal"),
        "smc_options_hint": row.get("smc_options_hint"),
        "smc_context": row.get("smc_context"),
        "smc_bias": row.get("smc_bias"),
        "smc_range_position_pct": row.get("smc_range_position_pct"),
        "smc_rsi": row.get("smc_rsi"),
        "direction": direction,
    }
    event.update(
        compute_forward_metrics(
            df=df,
            index=index,
            horizons=horizons,
            direction=direction,
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
    max_horizon = max(horizons)
    if len(df) < min_bars + max_horizon:
        return []

    events: list[dict] = []
    start_index = max(min_bars - 1, 0)

    for i in range(start_index, len(df) - max_horizon):
        df_slice = df.iloc[: i + 1]
        for ranking_mode in ranking_modes:
            row = build_scanner_row(
                symbol=symbol,
                df_slice=df_slice,
                ranking_mode=ranking_mode,
                lux_analyzer=lux_analyzer,
                smc_analyzer=smc_analyzer,
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

        grouped = metric_df.groupby(SUMMARY_GROUP_COLUMNS, dropna=False, sort=False)
        for group_values, group in grouped:
            directional = group["directional_return"].dropna()
            wins = directional[directional > 0]
            losses = directional[directional < 0]
            directional_wins = group["win"].dropna()
            win_rate = (
                float(directional_wins.astype(float).mean())
                if not directional_wins.empty
                else None
            )
            avg_win = float(wins.mean()) if not wins.empty else None
            avg_loss = float(abs(losses.mean())) if not losses.empty else None
            expectancy = None
            if win_rate is not None and avg_win is not None and avg_loss is not None:
                expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)

            row = dict(zip(SUMMARY_GROUP_COLUMNS, group_values, strict=True))
            row["group_key"] = " | ".join(
                str(row[column]) for column in SUMMARY_GROUP_COLUMNS
            )
            row["horizon"] = horizon
            row["count"] = int(len(group))
            row["win_rate"] = win_rate
            row["avg_return"] = float(group["return"].mean())
            row["median_return"] = float(group["return"].median())
            row["avg_mfe"] = (
                float(group["mfe"].dropna().mean())
                if group["mfe"].notna().any()
                else None
            )
            row["avg_mae"] = (
                float(group["mae"].dropna().mean())
                if group["mae"].notna().any()
                else None
            )
            row["avg_win"] = avg_win
            row["avg_loss"] = avg_loss
            row["expectancy"] = expectancy
            rows.append(row)

    return rows


def backtest_universe(
    *,
    universe_file: str | Path,
    data_dir: str | Path,
    ranking_mode: str,
    min_bars: int = DEFAULT_MIN_BARS,
    horizons: list[int] | None = None,
    win_threshold: float = DEFAULT_WIN_THRESHOLD,
    output_events: str | Path = "reports/options_scanner/backtest_v3_events.csv",
    output_summary: str | Path = "reports/options_scanner/backtest_v3_summary.csv",
    symbols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    horizons = horizons or list(DEFAULT_HORIZONS)
    ranking_modes = _resolve_ranking_modes(ranking_mode)
    universe = load_universe(universe_file)
    selected_symbols = (
        {symbol.upper() for symbol in symbols} if symbols is not None else None
    )

    lux_analyzer = StockDataAnalyzer(signal_model="lux")
    smc_analyzer = StockDataAnalyzer(signal_model="smc")
    events: list[dict] = []

    for entry in universe.itertuples(index=False):
        symbol = str(entry.symbol).upper()
        if selected_symbols is not None and symbol not in selected_symbols:
            continue

        try:
            df = load_symbol_csv(data_dir, symbol)
        except FileNotFoundError:
            continue

        events.extend(
            generate_symbol_events(
                symbol=symbol,
                df=df.sort_index(),
                ranking_modes=ranking_modes,
                min_bars=min_bars,
                horizons=horizons,
                win_threshold=win_threshold,
                lux_analyzer=lux_analyzer,
                smc_analyzer=smc_analyzer,
            )
        )

    events_df = pd.DataFrame(events)
    summary_df = pd.DataFrame(summarize_events(events, horizons))
    write_csv_report(events_df, output_events)
    write_csv_report(summary_df, output_summary)

    terminal_summary = render_backtest_summary(summary_df)
    if terminal_summary:
        print(terminal_summary)
    print(f"\nExported events: {Path(output_events)}")
    print(f"Exported summary: {Path(output_summary)}")
    return events_df, summary_df


def render_backtest_summary(summary_df: pd.DataFrame, limit: int = 12) -> str:
    if summary_df.empty:
        return "No backtest events generated."

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

    ordered = (
        summary_df.assign(
            _action_rank=summary_df["action_bucket"].map(action_priority).fillna(999),
            _strength_rank=summary_df["lux_strength"]
            .map(strength_priority)
            .fillna(999),
            _state_rank=summary_df["market_state"].map(state_priority).fillna(999),
            _horizon_rank=summary_df["horizon"].map(horizon_priority).fillna(999),
        )
        .sort_values(
            by=[
                "_action_rank",
                "_strength_rank",
                "_state_rank",
                "_horizon_rank",
                "count",
            ],
            ascending=[True, True, True, True, False],
        )
        .head(limit)
    )

    lines = []
    for row in ordered.itertuples(index=False):
        lines.append(
            f"{row.action_bucket} | {row.market_state} | {row.lux_strength} | "
            f"{row.ranking_mode} | h={row.horizon}"
        )
        win_rate = f"{row.win_rate * 100:.1f}%" if pd.notna(row.win_rate) else "n/a"
        avg_return = (
            f"{row.avg_return * 100:.1f}%" if pd.notna(row.avg_return) else "n/a"
        )
        expectancy = (
            f"{row.expectancy * 100:.1f}%" if pd.notna(row.expectancy) else "n/a"
        )
        lines.append(
            f"count={row.count} | win_rate={win_rate} | "
            f"avg_return={avg_return} | expectancy={expectancy}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Scanner V3 signal-quality backtest")
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
        default="reports/options_scanner/backtest_v3_events.csv",
    )
    parser.add_argument(
        "--output-summary",
        default="reports/options_scanner/backtest_v3_summary.csv",
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
    backtest_universe(
        universe_file=args.universe_file,
        data_dir=args.data_dir,
        ranking_mode=args.ranking_mode,
        min_bars=args.min_bars,
        horizons=_parse_horizons(args.horizons),
        win_threshold=args.win_threshold,
        output_events=args.output_events,
        output_summary=args.output_summary,
        symbols=_parse_symbols(args.symbols),
    )
    return 0


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

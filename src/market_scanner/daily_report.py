import argparse
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from tabulate import tabulate

from market_scanner.market_state import AVOID, CANDIDATE, NEEDS_REVIEW, WATCHLIST


DEFAULT_MAX_DAYS = 2
DEFAULT_TOP = 20

_PERCENT_COLUMNS = {"expectancy", "avg_mae"}

_FRESH_DISPLAY_COLUMNS = [
    "symbol",
    "action_bucket",
    "market_state",
    "lux_days_since_active_event",
    "lux_active_event",
    "smc_days_since_active_event",
    "smc_active_event",
]

_TOP_DISPLAY_COLUMNS = [
    "rank",
    "symbol",
    "side",
    "rec_source",
    "market_state",
    "consistency_score",
    "recommended_exit_rule",
    "expectancy",
    "profit_factor",
    "avg_mae",
    "total_trades",
]

_BUCKET_PRIORITY = {CANDIDATE: 0, WATCHLIST: 1, NEEDS_REVIEW: 2, AVOID: 3}

_REC_METRIC_COLUMNS = [
    "recommended_exit_rule",
    "expectancy",
    "profit_factor",
    "avg_mae",
    "total_trades",
]


@dataclass(frozen=True)
class CandidateSelection:
    top_df: pd.DataFrame
    candidate_count: int
    backtest_filter_applied: bool


def infer_side(adjusted_alignment: str) -> str | None:
    if adjusted_alignment == "bullish_aligned":
        return "bullish"
    if adjusted_alignment == "bearish_aligned":
        return "bearish"
    return None


def filter_fresh_signals(scan_df: pd.DataFrame, max_days: int) -> pd.DataFrame:
    lux_col = "lux_days_since_active_event"
    smc_col = "smc_days_since_active_event"

    lux_fresh = pd.Series(False, index=scan_df.index)
    smc_fresh = pd.Series(False, index=scan_df.index)

    if lux_col in scan_df.columns:
        lux_fresh = scan_df[lux_col].notna() & scan_df[lux_col].le(max_days)
    if smc_col in scan_df.columns:
        smc_fresh = scan_df[smc_col].notna() & scan_df[smc_col].le(max_days)

    return scan_df[lux_fresh | smc_fresh].copy()


def build_qualified_set(
    recommendations_df: pd.DataFrame,
) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    qualified = recommendations_df[recommendations_df["qualified"].eq(True)]

    symbol_recs = qualified[
        qualified["scope"].eq("symbol") & qualified["symbol"].notna()
    ]
    global_recs = qualified[qualified["scope"].eq("global")]

    symbol_pairs: set[tuple[str, str]] = set(
        zip(symbol_recs["symbol"], symbol_recs["side"])
    )
    global_sides: set[str] = set(global_recs["side"].dropna())
    symbols_with_symbol_rec: set[str] = set(symbol_recs["symbol"])

    return symbol_pairs, global_sides, symbols_with_symbol_rec


def _is_pair_qualified(
    symbol: str,
    side: str | None,
    symbol_pairs: set[tuple[str, str]],
    global_sides: set[str],
    symbols_with_symbol_rec: set[str],
) -> bool:
    if side is None:
        return False
    if (symbol, side) in symbol_pairs:
        return True
    if symbol not in symbols_with_symbol_rec and side in global_sides:
        return True
    return False


def _get_recommendation_metrics(
    symbol: str,
    side: str | None,
    qualified_recs: pd.DataFrame,
) -> dict:
    empty: dict = {col: pd.NA for col in _REC_METRIC_COLUMNS}
    empty["rec_source"] = "—"
    if side is None or qualified_recs.empty:
        return empty

    symbol_row = qualified_recs[
        qualified_recs["scope"].eq("symbol")
        & qualified_recs["symbol"].eq(symbol)
        & qualified_recs["side"].eq(side)
    ]
    if not symbol_row.empty:
        row = symbol_row.iloc[0]
        result = {col: row.get(col, pd.NA) for col in _REC_METRIC_COLUMNS}
        result["rec_source"] = "symbol"
        return result

    global_row = qualified_recs[
        qualified_recs["scope"].eq("global") & qualified_recs["side"].eq(side)
    ]
    if not global_row.empty:
        row = global_row.iloc[0]
        result = {col: row.get(col, pd.NA) for col in _REC_METRIC_COLUMNS}
        result["rec_source"] = "global"
        return result

    return empty


def build_top_candidates(
    fresh_df: pd.DataFrame,
    qualified_recs: pd.DataFrame | None,
    top: int,
) -> pd.DataFrame:
    return build_candidate_selection(fresh_df, qualified_recs, top).top_df


def build_candidate_selection(
    fresh_df: pd.DataFrame,
    recommendations_df: pd.DataFrame | None,
    top: int,
) -> CandidateSelection:
    candidates = fresh_df[fresh_df["action_bucket"].eq(CANDIDATE)].copy()
    if candidates.empty:
        return CandidateSelection(
            top_df=pd.DataFrame(),
            candidate_count=0,
            backtest_filter_applied=_has_recommendations(recommendations_df),
        )

    if "adjusted_alignment" in candidates.columns:
        candidates["side"] = candidates["adjusted_alignment"].map(infer_side)
    else:
        candidates["side"] = None

    backtest_filter_applied = _has_recommendations(recommendations_df)
    qualified_recs = _filter_qualified_recommendations(recommendations_df)
    if backtest_filter_applied:
        symbol_pairs, global_sides, symbols_with_symbol_rec = build_qualified_set(
            qualified_recs
        )
        mask = candidates.apply(
            lambda row: _is_pair_qualified(
                row["symbol"],
                row.get("side"),
                symbol_pairs,
                global_sides,
                symbols_with_symbol_rec,
            ),
            axis=1,
        )
        candidates = candidates[mask].copy()

    candidate_count = len(candidates)
    if candidates.empty:
        return CandidateSelection(
            top_df=pd.DataFrame(),
            candidate_count=candidate_count,
            backtest_filter_applied=backtest_filter_applied,
        )

    if "consistency_score" in candidates.columns:
        candidates = candidates.sort_values(
            "consistency_score", ascending=False, na_position="last"
        )

    top_df = candidates.head(top).copy()
    top_df.insert(0, "rank", range(1, len(top_df) + 1))

    if backtest_filter_applied:
        metrics = top_df.apply(
            lambda row: _get_recommendation_metrics(
                row["symbol"], row.get("side"), qualified_recs
            ),
            axis=1,
        )
        metrics_df = pd.DataFrame(list(metrics), index=top_df.index)
        for col in metrics_df.columns:
            top_df[col] = metrics_df[col]
    else:
        for col in _REC_METRIC_COLUMNS:
            top_df[col] = pd.NA
        top_df["rec_source"] = "—"

    return CandidateSelection(
        top_df=top_df,
        candidate_count=candidate_count,
        backtest_filter_applied=backtest_filter_applied,
    )


def _has_recommendations(recommendations_df: pd.DataFrame | None) -> bool:
    return recommendations_df is not None and not recommendations_df.empty


def _filter_qualified_recommendations(
    recommendations_df: pd.DataFrame | None,
) -> pd.DataFrame:
    if recommendations_df is None or recommendations_df.empty:
        return pd.DataFrame()
    return recommendations_df[recommendations_df["qualified"].eq(True)].copy()


def build_bucket_summary(scan_df: pd.DataFrame) -> pd.DataFrame:
    if "action_bucket" not in scan_df.columns or scan_df.empty:
        return pd.DataFrame(columns=["bucket", "count"])

    summary = (
        scan_df.groupby("action_bucket", as_index=False)
        .size()
        .rename(columns={"action_bucket": "bucket", "size": "count"})
    )
    summary["_priority"] = summary["bucket"].map(_BUCKET_PRIORITY).fillna(99)
    return summary.sort_values("_priority").drop(columns="_priority")


def render_daily_report(
    scan_df: pd.DataFrame,
    recommendations_df: pd.DataFrame | None = None,
    *,
    max_days: int = DEFAULT_MAX_DAYS,
    top: int = DEFAULT_TOP,
    generated_at: datetime | None = None,
) -> str:
    if generated_at is None:
        generated_at = datetime.now(UTC)

    date_str = generated_at.strftime("%Y-%m-%d")
    fresh_df = filter_fresh_signals(scan_df, max_days)
    fresh_candidates_df = (
        fresh_df[fresh_df["action_bucket"].eq(CANDIDATE)].copy()
        if not fresh_df.empty
        else fresh_df.copy()
    )
    candidate_selection = build_candidate_selection(fresh_df, recommendations_df, top)
    top_df = candidate_selection.top_df
    bucket_summary = build_bucket_summary(scan_df)
    top_count = len(top_df) if not top_df.empty else 0
    if candidate_selection.backtest_filter_applied:
        candidate_count_line = (
            f"- Qualificados pelo backtest: {candidate_selection.candidate_count}"
        )
    else:
        candidate_count_line = (
            "- Candidatos frescos (sem filtro backtest): "
            f"{candidate_selection.candidate_count}"
        )

    lines = [
        f"# Daily Report — {date_str}",
        "",
        f"## 1. Sinais Frescos — Candidates (últimos {max_days} dias)",
        "",
        _fresh_table(fresh_candidates_df),
        "",
        f"## 2. Top {top} Operacional",
        "",
        _top_table(top_df),
        "",
        "## 3. Sumário por Bucket",
        "",
        _bucket_table(bucket_summary),
        "",
        "## 4. Stats",
        "",
        f"- Total símbolos no scan: {len(scan_df)}",
        f"- Com sinal fresco (≤ {max_days} dias): {len(fresh_df)}",
        f"- Candidates frescos: {len(fresh_candidates_df)}",
        candidate_count_line,
        f"- No Top {top}: {top_count}",
        "",
    ]
    return "\n".join(lines)


def _fresh_table(fresh_df: pd.DataFrame) -> str:
    if fresh_df.empty:
        return "_No fresh signals._"

    col_rename = {
        "lux_days_since_active_event": "lux_days",
        "lux_active_event": "lux_event",
        "smc_days_since_active_event": "smc_days",
        "smc_active_event": "smc_event",
    }
    display = fresh_df.loc[
        :, [c for c in _FRESH_DISPLAY_COLUMNS if c in fresh_df.columns]
    ].copy()
    display = display.rename(columns=col_rename)
    display = display.fillna("—")
    return tabulate(display, headers="keys", tablefmt="github", showindex=False)


def _top_table(top_df: pd.DataFrame) -> str:
    if top_df.empty:
        return "_No qualified candidates._"

    display = top_df.loc[
        :, [c for c in _TOP_DISPLAY_COLUMNS if c in top_df.columns]
    ].copy()

    for col in display.columns:
        if col in _PERCENT_COLUMNS:
            display[col] = display[col].map(_format_percent)
        elif col == "profit_factor":
            display[col] = display[col].map(_format_decimal)
        elif col == "total_trades":
            rec_source_col = (
                display.get("rec_source") if "rec_source" in display.columns else None
            )
            display[col] = display.apply(
                lambda r, c=col: "global"
                if (rec_source_col is not None and r.get("rec_source") == "global")
                else ("—" if pd.isna(r[c]) else r[c]),
                axis=1,
            )
        else:
            display[col] = display[col].fillna("—")

    return tabulate(display, headers="keys", tablefmt="github", showindex=False)


def _bucket_table(bucket_df: pd.DataFrame) -> str:
    if bucket_df.empty:
        return "_No data._"
    return tabulate(bucket_df, headers="keys", tablefmt="github", showindex=False)


def _format_percent(value) -> str:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return "—"
    return f"{float(converted) * 100.0:.2f}%"


def _format_decimal(value) -> str:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return "—"
    return f"{float(converted):.2f}"


def write_daily_report(
    *,
    scan_path: str | Path,
    recommendations_path: str | Path | None = None,
    output_path: str | Path,
    output_candidates: str | Path | None = None,
    archive_dir: str | Path | None = None,
    max_days: int = DEFAULT_MAX_DAYS,
    top: int = DEFAULT_TOP,
) -> str:
    """Write the Markdown report to disk and return the report content."""
    scan_df = pd.read_csv(scan_path)
    recommendations_df: pd.DataFrame | None = None
    if recommendations_path is not None:
        rec_path = Path(recommendations_path)
        if rec_path.exists():
            recommendations_df = pd.read_csv(rec_path)

    report = render_daily_report(
        scan_df,
        recommendations_df,
        max_days=max_days,
        top=top,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")

    if archive_dir is not None:
        archive = Path(archive_dir)
        archive.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")

        dated_md = archive / f"{date_str}.md"
        dated_md.write_text(report, encoding="utf-8")

        if output_candidates is not None and Path(output_candidates).exists():
            dated_csv = archive / f"{date_str}_candidates.csv"
            shutil.copy(output_candidates, dated_csv)

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Market scanner daily operational report")
    parser.add_argument("--scan", required=True, help="scan CSV from scan.py")
    parser.add_argument(
        "--recommendations",
        default=None,
        help="execution_recommended_rules.csv (optional)",
    )
    parser.add_argument("--max-days", type=int, default=DEFAULT_MAX_DAYS)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument(
        "--output",
        default="reports/market_scanner/daily_report.md",
    )
    parser.add_argument(
        "--output-candidates",
        default=None,
        help="Path for candidates CSV output (optional)",
    )
    parser.add_argument(
        "--archive-dir",
        default=None,
        help="Directory to save a dated copy: YYYY-MM-DD.md and YYYY-MM-DD_candidates.csv",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    write_daily_report(
        scan_path=args.scan,
        recommendations_path=args.recommendations,
        output_path=args.output,
        output_candidates=args.output_candidates,
        archive_dir=args.archive_dir,
        max_days=args.max_days,
        top=args.top,
    )
    print(f"Exported daily report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pandas as pd
from tabulate import tabulate


DEFAULT_REPORTS_DIR = Path("reports/market_scanner")
DEFAULT_RECOMMENDATIONS = DEFAULT_REPORTS_DIR / "execution_recommended_rules.csv"
DEFAULT_SYMBOL_COMPARISON = DEFAULT_REPORTS_DIR / "execution_symbol_comparison.csv"
DEFAULT_SCAN = DEFAULT_REPORTS_DIR / "scan.csv"
DEFAULT_OUTPUT_MD = DEFAULT_REPORTS_DIR / "execution_operational_report.md"
DEFAULT_OUTPUT_RANKING = DEFAULT_REPORTS_DIR / "execution_operational_ranking.csv"

RANKING_COLUMNS = [
    "rank",
    "symbol",
    "classification",
    "side",
    "recommended_exit_rule",
    "qualified",
    "qualification_reason",
    "total_trades",
    "win_rate",
    "expectancy",
    "profit_factor",
    "avg_bars_held",
    "avg_mfe",
    "avg_mae",
    "best_trade",
    "worst_trade",
    "performance_score",
    "action_bucket",
    "market_state",
    "adjusted_alignment",
]


class OperationalReport(NamedTuple):
    markdown: str
    ranking: pd.DataFrame


def build_operational_report(
    *,
    recommendations_df: pd.DataFrame,
    symbol_comparison_df: pd.DataFrame,
    scan_df: pd.DataFrame | None = None,
    generated_at: datetime | None = None,
    top: int = 50,
) -> OperationalReport:
    global_winners = _global_winners(recommendations_df)
    ranking = build_asset_ranking(
        recommendations_df=recommendations_df,
        symbol_comparison_df=symbol_comparison_df,
        scan_df=scan_df,
    )
    markdown = render_operational_report_markdown(
        global_winners=global_winners,
        ranking=ranking,
        generated_at=generated_at or datetime.now(UTC),
        top=top,
    )
    return OperationalReport(markdown=markdown, ranking=ranking)


def build_asset_ranking(
    *,
    recommendations_df: pd.DataFrame,
    symbol_comparison_df: pd.DataFrame,
    scan_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    symbol_recommendations = recommendations_df[
        recommendations_df["scope"].eq("symbol")
    ].copy()
    if symbol_recommendations.empty:
        return pd.DataFrame(columns=RANKING_COLUMNS)

    symbol_recommendations["performance_score"] = symbol_recommendations.apply(
        _performance_score,
        axis=1,
    )
    symbol_recommendations["classification"] = symbol_recommendations.apply(
        _classify_recommendation,
        axis=1,
    )

    ranked = (
        symbol_recommendations.sort_values(
            [
                "symbol",
                "qualified",
                "performance_score",
                "total_trades",
                "profit_factor",
            ],
            ascending=[True, False, False, False, False],
            na_position="last",
        )
        .groupby("symbol", as_index=False, sort=True)
        .head(1)
        .copy()
    )

    ranked["_classification_priority"] = ranked["classification"].map(
        {
            "trade_candidate": 0,
            "watchlist": 1,
            "risk_review": 2,
            "avoid": 3,
        }
    )
    ranked = ranked.sort_values(
        [
            "_classification_priority",
            "performance_score",
            "total_trades",
            "symbol",
        ],
        ascending=[True, False, False, True],
        na_position="last",
    ).drop(columns="_classification_priority")
    ranked.insert(0, "rank", range(1, len(ranked) + 1))

    if scan_df is not None and not scan_df.empty:
        scan_columns = [
            column
            for column in [
                "symbol",
                "action_bucket",
                "market_state",
                "adjusted_alignment",
            ]
            if column in scan_df.columns
        ]
        if "symbol" in scan_columns:
            latest_scan = scan_df.loc[:, scan_columns].drop_duplicates(
                subset=["symbol"],
                keep="first",
            )
            ranked = ranked.merge(latest_scan, on="symbol", how="left")

    for column in ["action_bucket", "market_state", "adjusted_alignment"]:
        if column not in ranked.columns:
            ranked[column] = pd.NA

    return ranked.loc[:, [column for column in RANKING_COLUMNS if column in ranked]]


def render_operational_report_markdown(
    *,
    global_winners: pd.DataFrame,
    ranking: pd.DataFrame,
    generated_at: datetime,
    top: int = 50,
) -> str:
    lines = [
        "# Execution Operational Report",
        "",
        f"Generated at: {generated_at.isoformat()}",
        "",
        "## Winning Strategy By Side",
        "",
        _markdown_table(global_winners, _GLOBAL_DISPLAY_COLUMNS),
        "",
        "## Asset Classification",
        "",
        _markdown_table(
            _classification_summary(ranking), ["classification", "symbols"]
        ),
        "",
        f"## Top {top} Operational Ranking",
        "",
        _markdown_table(ranking.head(top), _RANKING_DISPLAY_COLUMNS),
        "",
        f"## Top {top} Symbol Recommendations",
        "",
        _markdown_table(ranking.head(top), _SYMBOL_DISPLAY_COLUMNS),
        "",
    ]
    return "\n".join(lines)


def write_operational_report(
    *,
    recommendations_path: str | Path = DEFAULT_RECOMMENDATIONS,
    symbol_comparison_path: str | Path = DEFAULT_SYMBOL_COMPARISON,
    scan_path: str | Path | None = DEFAULT_SCAN,
    output_markdown_path: str | Path = DEFAULT_OUTPUT_MD,
    output_ranking_path: str | Path = DEFAULT_OUTPUT_RANKING,
    top: int = 50,
) -> OperationalReport:
    recommendations_df = pd.read_csv(recommendations_path)
    symbol_comparison_df = pd.read_csv(symbol_comparison_path)
    scan_df = _read_optional_csv(scan_path)
    report = build_operational_report(
        recommendations_df=recommendations_df,
        symbol_comparison_df=symbol_comparison_df,
        scan_df=scan_df,
        top=top,
    )

    output_markdown = Path(output_markdown_path)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.write_text(report.markdown, encoding="utf-8")

    output_ranking = Path(output_ranking_path)
    output_ranking.parent.mkdir(parents=True, exist_ok=True)
    report.ranking.to_csv(output_ranking, index=False)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Market scanner operational report")
    parser.add_argument("--recommendations", default=str(DEFAULT_RECOMMENDATIONS))
    parser.add_argument("--symbol-comparison", default=str(DEFAULT_SYMBOL_COMPARISON))
    parser.add_argument(
        "--scan",
        default=str(DEFAULT_SCAN),
        help="Optional current scanner CSV used to attach action bucket/state columns.",
    )
    parser.add_argument("--output-markdown", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--output-ranking", default=str(DEFAULT_OUTPUT_RANKING))
    parser.add_argument("--top", type=int, default=50)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    write_operational_report(
        recommendations_path=args.recommendations,
        symbol_comparison_path=args.symbol_comparison,
        scan_path=args.scan,
        output_markdown_path=args.output_markdown,
        output_ranking_path=args.output_ranking,
        top=args.top,
    )
    print(f"Exported operational report: {args.output_markdown}")
    print(f"Exported operational ranking: {args.output_ranking}")
    return 0


_GLOBAL_DISPLAY_COLUMNS = [
    "side",
    "recommended_exit_rule",
    "total_trades",
    "win_rate",
    "expectancy",
    "profit_factor",
    "avg_bars_held",
    "worst_trade",
]
_RANKING_DISPLAY_COLUMNS = [
    "rank",
    "symbol",
    "classification",
    "side",
    "recommended_exit_rule",
    "performance_score",
    "total_trades",
    "win_rate",
    "expectancy",
    "profit_factor",
    "action_bucket",
    "market_state",
]
_SYMBOL_DISPLAY_COLUMNS = [
    "symbol",
    "side",
    "recommended_exit_rule",
    "classification",
    "total_trades",
    "win_rate",
    "expectancy",
    "avg_mfe",
    "avg_mae",
    "avg_bars_held",
]
_PERCENT_COLUMNS = {
    "win_rate",
    "expectancy",
    "avg_mfe",
    "avg_mae",
    "best_trade",
    "worst_trade",
}


def _global_winners(recommendations_df: pd.DataFrame) -> pd.DataFrame:
    winners = recommendations_df[recommendations_df["scope"].eq("global")].copy()
    return winners.sort_values(["side", "qualified"], ascending=[True, False])


def _performance_score(row: pd.Series) -> float:
    expectancy = _number(row.get("expectancy"))
    win_rate = _number(row.get("win_rate"))
    profit_factor = min(_number(row.get("profit_factor")), 5.0)
    avg_mae = abs(_number(row.get("avg_mae")))
    trade_depth = min(_number(row.get("total_trades")) / 100.0, 1.0)
    return round(
        expectancy * 100.0
        + (win_rate - 0.5) * 20.0
        + profit_factor
        + trade_depth
        - avg_mae * 25.0,
        4,
    )


def _classify_recommendation(row: pd.Series) -> str:
    if not bool(row.get("qualified")):
        return "avoid"

    expectancy = _number(row.get("expectancy"))
    profit_factor = _number(row.get("profit_factor"))
    total_trades = _number(row.get("total_trades"))
    avg_mae = _number(row.get("avg_mae"))
    worst_trade = _number(row.get("worst_trade"))

    if expectancy <= 0 or profit_factor < 1.0:
        return "avoid"
    if avg_mae <= -0.15 or worst_trade <= -0.50:
        return "risk_review"
    if total_trades >= 20 and expectancy >= 0.02 and profit_factor >= 1.5:
        return "trade_candidate"
    return "watchlist"


def _classification_summary(ranking: pd.DataFrame) -> pd.DataFrame:
    if ranking.empty:
        return pd.DataFrame(columns=["classification", "symbols"])
    summary = (
        ranking.groupby("classification", as_index=False)
        .size()
        .rename(columns={"size": "symbols"})
    )
    summary["_priority"] = summary["classification"].map(
        {
            "trade_candidate": 0,
            "watchlist": 1,
            "risk_review": 2,
            "avoid": 3,
        }
    )
    return summary.sort_values("_priority").drop(columns="_priority")


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_No rows._"

    display = df.loc[:, [column for column in columns if column in df.columns]].copy()
    for column in display.columns:
        if column in _PERCENT_COLUMNS:
            display[column] = display[column].map(_format_percent)
        elif pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(_format_decimal)
        else:
            display[column] = display[column].fillna("-")
    return tabulate(display, headers="keys", tablefmt="github", showindex=False)


def _read_optional_csv(path: str | Path | None) -> pd.DataFrame | None:
    if path is None or str(path).strip() == "":
        return None
    csv_path = Path(path)
    if not csv_path.exists():
        return None
    return pd.read_csv(csv_path)


def _number(value) -> float:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return 0.0
    return float(converted)


def _format_percent(value) -> str:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return "-"
    return f"{float(converted) * 100.0:.2f}%"


def _format_decimal(value) -> str:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return "-"
    return f"{float(converted):.2f}"


if __name__ == "__main__":
    raise SystemExit(main())

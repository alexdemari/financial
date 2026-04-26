from pathlib import Path

import pandas as pd
from tabulate import tabulate

from market_scanner.market_state import (
    AVOID,
    CANDIDATE,
    NEEDS_REVIEW,
    WATCHLIST,
    EARLY_TREND,
    PULLBACK,
    RANGE,
    EXTENDED,
    EXHAUSTION,
    UNKNOWN,
)


TERMINAL_COLUMNS = [
    "symbol",
    "close",
    "lux_trend",
    "lux_strength",
    "smc_range_position_pct",
    "smc_rsi",
    "alignment",
    "adjusted_alignment",
    "market_state",
    "action_bucket",
    "consistency_score",
]

ACTION_BUCKET_PRIORITY = {
    CANDIDATE: 0,
    WATCHLIST: 1,
    NEEDS_REVIEW: 2,
    AVOID: 3,
}

MARKET_STATE_PRIORITY = {
    EARLY_TREND: 0,
    PULLBACK: 1,
    RANGE: 2,
    EXTENDED: 3,
    EXHAUSTION: 4,
    UNKNOWN: 5,
}

ALIGNMENT_PRIORITY = {
    "bullish_aligned": 0,
    "bearish_aligned": 1,
    "bullish_watchlist": 2,
    "bearish_watchlist": 3,
    "range_watchlist": 4,
    "mixed": 5,
    "no_trade": 6,
}


def write_csv_report(df: pd.DataFrame, output_path: str | Path) -> Path:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(report_path, index=False)
    return report_path


def render_top_n_summary(df: pd.DataFrame, top: int) -> str:
    if df.empty:
        return "No eligible scanner results."

    top_rows = sort_scanner_results(df).head(top)
    display = top_rows.loc[
        :, [col for col in TERMINAL_COLUMNS if col in top_rows.columns]
    ].copy()

    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: f"{value:.2f}" if pd.notna(value) else "-"
            )
    return tabulate(display, headers="keys", tablefmt="simple", showindex=False)


def sort_scanner_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    sortable = df.copy()
    if "eligible" not in sortable.columns:
        sortable["eligible"] = True
    sortable["_bucket_priority"] = (
        sortable["action_bucket"]
        .map(ACTION_BUCKET_PRIORITY)
        .fillna(len(ACTION_BUCKET_PRIORITY))
    )
    sortable["_state_priority"] = (
        sortable["market_state"]
        .map(MARKET_STATE_PRIORITY)
        .fillna(len(MARKET_STATE_PRIORITY))
    )
    sortable["_alignment_priority"] = (
        sortable["adjusted_alignment"]
        .map(ALIGNMENT_PRIORITY)
        .fillna(len(ALIGNMENT_PRIORITY))
    )

    return sortable.sort_values(
        [
            "eligible",
            "_bucket_priority",
            "_state_priority",
            "_alignment_priority",
            "consistency_score",
            "symbol",
        ],
        ascending=[False, True, True, True, False, True],
        na_position="last",
    ).drop(columns=["_bucket_priority", "_state_priority", "_alignment_priority"])

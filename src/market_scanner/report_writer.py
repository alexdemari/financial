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

SMC_TERMINAL_COLUMNS = [
    "symbol",
    "close",
    "avg_dollar_volume_20",
    "market_cap",
    "smc_role",
    "smc_active_event",
    "smc_active_event_options_hint",
    "smc_active_event_context",
    "smc_days_since_active_event",
    "lux_trend",
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

SMC_ROLE_PRIORITY = {
    "bullish_trigger": 0,
    "bearish_trigger": 1,
    "bullish_watch": 2,
    "bearish_watch": 3,
    "neutral": 4,
}


def write_csv_report(df: pd.DataFrame, output_path: str | Path) -> Path:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(report_path, index=False)
    return report_path


def render_top_n_summary(df: pd.DataFrame, top: int, sort_by: str = "scanner") -> str:
    if df.empty:
        return "No eligible scanner results."

    top_rows = sort_scanner_results(df, sort_by=sort_by).head(top)
    terminal_columns = (
        SMC_TERMINAL_COLUMNS if sort_by == "smc-recent" else TERMINAL_COLUMNS
    )
    display = top_rows.loc[
        :, [col for col in terminal_columns if col in top_rows.columns]
    ].copy()

    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: f"{value:.2f}" if pd.notna(value) else "-"
            )
    return tabulate(display, headers="keys", tablefmt="simple", showindex=False)


def sort_scanner_results(df: pd.DataFrame, sort_by: str = "scanner") -> pd.DataFrame:
    if df.empty:
        return df

    sortable = df.copy()
    if "eligible" not in sortable.columns:
        sortable["eligible"] = True
    if sort_by == "smc-recent":
        return _sort_by_smc_recent(sortable)

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


def _sort_by_smc_recent(df: pd.DataFrame) -> pd.DataFrame:
    sortable = df.copy()
    sortable["_smc_role_priority"] = (
        sortable["smc_role"].map(SMC_ROLE_PRIORITY).fillna(len(SMC_ROLE_PRIORITY))
    )
    sortable["_has_smc_active_event"] = sortable["smc_active_event"].notna()
    sortable["_bucket_priority"] = (
        sortable["action_bucket"]
        .map(ACTION_BUCKET_PRIORITY)
        .fillna(len(ACTION_BUCKET_PRIORITY))
    )

    return sortable.sort_values(
        [
            "eligible",
            "_has_smc_active_event",
            "_smc_role_priority",
            "smc_days_since_active_event",
            "consistency_score",
            "_bucket_priority",
            "symbol",
        ],
        ascending=[False, False, True, True, False, True, True],
        na_position="last",
    ).drop(columns=["_smc_role_priority", "_has_smc_active_event", "_bucket_priority"])

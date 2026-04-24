from pathlib import Path

import pandas as pd
from tabulate import tabulate


SNAPSHOT_TERMINAL_COLUMNS = [
    "symbol",
    "close",
    "avg_volume_20",
    "market_cap",
    "lux_options_hint",
    "smc_options_hint",
    "alignment",
    "consistency_score",
]

RECENT_EVENT_TERMINAL_COLUMNS = [
    "symbol",
    "close",
    "avg_volume_20",
    "market_cap",
    "lux_active_event_options_hint",
    "lux_days_since_active_event",
    "smc_active_event_options_hint",
    "smc_days_since_active_event",
    "alignment",
    "consistency_score",
]


def write_csv_report(df: pd.DataFrame, output_path: str | Path) -> Path:
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(report_path, index=False)
    return report_path


def render_top_n_summary(df: pd.DataFrame, top: int) -> str:
    if df.empty:
        return "No eligible scanner results."

    top_rows = df.sort_values(
        ["consistency_score", "symbol"], ascending=[False, True]
    ).head(top)
    terminal_columns = _terminal_columns_for_mode(top_rows)
    display = top_rows.loc[
        :, [col for col in terminal_columns if col in top_rows.columns]
    ].copy()

    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: f"{value:.2f}" if pd.notna(value) else "-"
            )
    return tabulate(display, headers="keys", tablefmt="simple", showindex=False)


def _terminal_columns_for_mode(df: pd.DataFrame) -> list[str]:
    if "ranking_mode" not in df.columns:
        return SNAPSHOT_TERMINAL_COLUMNS

    modes = df["ranking_mode"].dropna().astype(str)
    if not modes.empty and modes.iloc[0] == "recent-event":
        return RECENT_EVENT_TERMINAL_COLUMNS

    return SNAPSHOT_TERMINAL_COLUMNS

from pathlib import Path

import pandas as pd
from tabulate import tabulate


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
    display = top_rows.loc[
        :, [col for col in TERMINAL_COLUMNS if col in top_rows.columns]
    ].copy()

    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: f"{value:.2f}" if pd.notna(value) else "-"
            )
    return tabulate(display, headers="keys", tablefmt="simple", showindex=False)

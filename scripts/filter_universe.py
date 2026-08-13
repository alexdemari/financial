"""Shrink the scanner universe CSV by market_cap and dollar-volume thresholds.

Filters data/scanner_universe_filtered.csv down to symbols that would pass
market_scanner.eligibility's gate, so stock_data_manager doesn't waste daily
downloads on symbols that get excluded downstream anyway.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

DEFAULT_MIN_MARKET_CAP = 1_000_000_000.0
DEFAULT_MIN_AVG_DOLLAR_VOLUME_20 = 5_000_000.0


def filter_universe(
    universe_df: pd.DataFrame,
    min_market_cap: float,
    min_avg_dollar_volume_20: float,
) -> pd.DataFrame:
    eligible = (universe_df["market_cap"] >= min_market_cap) & (
        universe_df["avg_dollar_volume_20"] >= min_avg_dollar_volume_20
    )
    return universe_df[eligible].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-file", default="data/scanner_universe_filtered.csv")
    parser.add_argument("--min-market-cap", type=float, default=DEFAULT_MIN_MARKET_CAP)
    parser.add_argument(
        "--min-avg-dollar-volume-20",
        type=float,
        default=DEFAULT_MIN_AVG_DOLLAR_VOLUME_20,
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report counts without writing the file"
    )
    args = parser.parse_args()

    universe_path = Path(args.universe_file)
    universe_df = pd.read_csv(universe_path)
    before_count = len(universe_df)

    filtered_df = filter_universe(
        universe_df, args.min_market_cap, args.min_avg_dollar_volume_20
    )
    after_count = len(filtered_df)

    print(
        f"{universe_path}: {before_count} -> {after_count} symbols "
        f"(min_market_cap={args.min_market_cap:,.0f}, "
        f"min_avg_dollar_volume_20={args.min_avg_dollar_volume_20:,.0f})"
    )

    if args.dry_run:
        return

    backup_path = universe_path.with_suffix(universe_path.suffix + ".bak")
    shutil.copy2(universe_path, backup_path)
    filtered_df.to_csv(universe_path, index=False)
    print(f"Backup written to {backup_path}")


if __name__ == "__main__":
    main()

"""Fetch the IBKR Flex Query configured for Cash Transactions / Change in NAV.

Shares the SendRequest/GetStatement workflow (retry, backoff, error handling)
with ``ibkr_trades.flex_fetcher`` but points at a separate Flex Query id,
since Cash Transactions and Trades are configured as distinct queries in the
IBKR Client Portal. Reuses the same ``IBKR_FLEX_TOKEN``.

IBKR Flex Queries typically cap lookback at ~1 year; this module does not
attempt to backfill beyond whatever the configured query's date range covers.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ibkr_trades.flex_fetcher import fetch_flex_query

QUERY_ID_ENV = "IBKR_FLEX_QUERY_ID_CASH"


def fetch_cash_flex_query(
    output_path: Path,
    *,
    initial_wait: float = 5.0,
    wait_cap: float = 30.0,
    max_total_wait: float = 120.0,
) -> Path | None:
    """Poll GetStatement with exponential backoff (5s → 30s cap, 120s budget)."""
    return fetch_flex_query(
        output_path,
        query_id_env=QUERY_ID_ENV,
        retry_wait=initial_wait,
        statement_wait_cap=wait_cap,
        statement_max_total_wait=max_total_wait,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the latest IBKR Cash Transactions Flex Query XML."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/ibkr/flex_cash_latest.xml"),
        help="destination XML path (default: data/ibkr/flex_cash_latest.xml)",
    )
    arguments = parser.parse_args()
    result = fetch_cash_flex_query(arguments.output)
    if result is None:
        print("Skipped; using existing file.")


if __name__ == "__main__":
    main()

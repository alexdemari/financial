"""CLI entry point for ibkr_cash.

Commands:
  sync    Parse Cash Transactions Flex XML, upsert into local CSV stores
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ibkr_cash.flex_parser import parse_cash_transactions, parse_nav_changes
from ibkr_cash.store import (
    CASH_TRANSACTIONS_PATH,
    NAV_CHANGES_PATH,
    upsert_cash_transactions,
    upsert_nav_changes,
)


def cmd_sync(args: argparse.Namespace) -> int:
    flex_path = Path(args.flex)
    if not flex_path.exists():
        print(f"Error: Flex XML not found: {flex_path}", file=sys.stderr)
        return 1

    cash_transactions = parse_cash_transactions(flex_path)
    nav_changes = parse_nav_changes(flex_path)

    cash_path = Path(args.cash_transactions)
    nav_path = Path(args.nav_changes)

    cash_added, cash_updated = upsert_cash_transactions(cash_transactions, cash_path)
    nav_added, nav_updated = upsert_nav_changes(nav_changes, nav_path)

    dates = sorted(t.date for t in cash_transactions if t.date)
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "n/a"

    print(
        f"Cash transactions: {cash_added} added, {cash_updated} updated ({cash_path})"
    )
    print(f"NAV changes:        {nav_added} added, {nav_updated} updated ({nav_path})")
    print(f"Date range covered: {date_range}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR cash transactions / NAV tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Parse Flex XML, upsert local CSV stores")
    p_sync.add_argument("--flex", required=True, help="Path to Flex Query XML export")
    p_sync.add_argument("--cash-transactions", default=str(CASH_TRANSACTIONS_PATH))
    p_sync.add_argument("--nav-changes", default=str(NAV_CHANGES_PATH))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "sync":
        return cmd_sync(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

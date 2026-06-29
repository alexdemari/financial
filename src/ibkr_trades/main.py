"""CLI entry point for ibkr_trades.

Commands:
  backfill          Parse Flex Query XML, write trades_history.csv
  sync              Fetch new executions from IB Gateway, append to history
  generate-tracker  Derive options_tracker.csv from trade history (offline, read-only)
  full              sync + generate-tracker
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from ibkr_trades.flex_parser import parse_flex_xml
from ibkr_trades.roll_detector import detect_and_tag_rolls
from ibkr_trades.store import HISTORY_PATH, append_trades, last_sync_date
from ibkr_trades.strategy_tagger import tag_strategies
from ibkr_trades.tracker_builder import build_options_tracker

_DEFAULT_TRACKER = Path("options_tracker.csv")
_DEFAULT_BACKUP_DIR = Path("data/ibkr")


def _tag_history(path: Path) -> None:
    """Apply roll detection and strategy tagging to history after an append.

    Only fills null roll_id and strategy fields; other columns are untouched.
    This is the sole permitted mutation of stored history rows.
    """
    df = pd.read_csv(path, dtype={"trade_id": str, "roll_id": str, "strategy": str})
    df = detect_and_tag_rolls(df)
    df = tag_strategies(df)
    df.to_csv(path, index=False)


def cmd_backfill(args: argparse.Namespace) -> int:
    flex_path = Path(args.flex)
    if not flex_path.exists():
        print(f"Error: Flex XML not found: {flex_path}", file=sys.stderr)
        return 1

    history_path = Path(args.history)
    print(f"Parsing {flex_path} ...")
    records = parse_flex_xml(flex_path)
    print(f"  Parsed {len(records)} trades from Flex XML")

    added, skipped = append_trades(records, history_path)
    print(f"  Added {added} new trades, skipped {skipped} duplicates")

    if added > 0:
        print("  Tagging rolls and strategies ...")
        _tag_history(history_path)

    print(f"  History: {history_path}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from ib_insync import IB

    from ibkr_trades.api_fetcher import fetch_recent_trades

    history_path = Path(args.history)
    since = last_sync_date(history_path)
    print(f"Connecting to IB Gateway at {args.host}:{args.port} ...")

    ib = IB()
    try:
        ib.connect(
            args.host, args.port, clientId=args.client_id, readonly=True, timeout=10
        )
    except Exception as exc:
        print(f"Error: cannot connect to IB Gateway: {exc}", file=sys.stderr)
        return 1

    try:
        accounts = ib.managedAccounts()
        account_id = accounts[0] if accounts else ""
        print(f"  Account: {account_id}, fetching since {since} ...")
        records = fetch_recent_trades(ib, account_id, since=since)
    finally:
        ib.disconnect()

    print(f"  Fetched {len(records)} executions")
    added, skipped = append_trades(records, history_path)
    print(f"  Added {added} new trades, skipped {skipped} duplicates")

    if added > 0:
        print("  Tagging rolls and strategies ...")
        _tag_history(history_path)

    return 0


def cmd_generate_tracker(args: argparse.Namespace) -> int:
    """Derive options_tracker.csv from trade history. Read-only: does not modify history."""
    history_path = Path(args.history)
    tracker_path = Path(args.tracker)
    backup_dir = Path(args.backup_dir)

    if not history_path.exists():
        print(f"Error: history not found: {history_path}", file=sys.stderr)
        return 1

    n = build_options_tracker(history_path, tracker_path, backup_dir)
    print(f"  Wrote {n} open legs to {tracker_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR trade history tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    # backfill
    p_bf = sub.add_parser(
        "backfill", help="Parse Flex XML, populate trades_history.csv"
    )
    p_bf.add_argument("--flex", required=True, help="Path to Flex Query XML export")
    p_bf.add_argument("--history", default=str(HISTORY_PATH))

    # sync
    p_sync = sub.add_parser("sync", help="Fetch new executions from IB Gateway")
    p_sync.add_argument("--host", default="127.0.0.1")
    p_sync.add_argument("--port", type=int, default=7496)
    p_sync.add_argument("--client-id", type=int, default=11, dest="client_id")
    p_sync.add_argument("--history", default=str(HISTORY_PATH))

    # generate-tracker
    p_gt = sub.add_parser(
        "generate-tracker", help="Derive options_tracker.csv from history"
    )
    p_gt.add_argument("--history", default=str(HISTORY_PATH))
    p_gt.add_argument("--tracker", default=str(_DEFAULT_TRACKER))
    p_gt.add_argument(
        "--backup-dir", default=str(_DEFAULT_BACKUP_DIR), dest="backup_dir"
    )

    # full = sync + generate-tracker
    p_full = sub.add_parser("full", help="sync + generate-tracker")
    p_full.add_argument("--host", default="127.0.0.1")
    p_full.add_argument("--port", type=int, default=7496)
    p_full.add_argument("--client-id", type=int, default=11, dest="client_id")
    p_full.add_argument("--history", default=str(HISTORY_PATH))
    p_full.add_argument("--tracker", default=str(_DEFAULT_TRACKER))
    p_full.add_argument(
        "--backup-dir", default=str(_DEFAULT_BACKUP_DIR), dest="backup_dir"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "backfill":
        return cmd_backfill(args)
    if args.command == "sync":
        return cmd_sync(args)
    if args.command == "generate-tracker":
        return cmd_generate_tracker(args)
    if args.command == "full":
        rc = cmd_sync(args)
        if rc != 0:
            return rc
        return cmd_generate_tracker(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

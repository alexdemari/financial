from __future__ import annotations

import argparse
import sys

from ibkr_positions.client import IBKRClient, IBKRConnectionError
from ibkr_positions.options_export import write_options_tracker_live_csv
from ibkr_positions.report import write_positions_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR portfolio positions risk report")
    parser.add_argument(
        "--output-dir",
        default="reports/output",
        help="Directory to write report files (default: reports/output)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="IB Gateway host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7496,
        help="IB Gateway TWS API port (default: 7496)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=10,
        help="TWS API client ID (default: 10)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = IBKRClient(host=args.host, port=args.port, client_id=args.client_id)
    try:
        portfolio = client.get_portfolio()
    except IBKRConnectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    md_path, csv_path, html_path = write_positions_report(
        portfolio, output_dir=args.output_dir
    )
    options_csv_path = write_options_tracker_live_csv(
        portfolio, output_dir=args.output_dir
    )
    print(f"Report: {md_path}")
    print(f"CSV:    {csv_path}")
    print(f"HTML:   {html_path}")
    print(f"Options CSV: {options_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

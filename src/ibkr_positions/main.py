from __future__ import annotations

import argparse
import sys

from ibkr_positions.client import IBKRClient, IBKRConnectionError
from ibkr_positions.report import write_positions_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR portfolio positions risk report")
    parser.add_argument(
        "--output-dir",
        default="reports/output",
        help="Directory to write report files (default: reports/output)",
    )
    parser.add_argument(
        "--gateway-url",
        default="https://localhost:5000",
        help="IBKR Client Portal gateway URL (default: https://localhost:5000)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    client = IBKRClient(gateway_url=args.gateway_url)
    try:
        portfolio = client.get_portfolio()
    except IBKRConnectionError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    md_path, csv_path = write_positions_report(portfolio, output_dir=args.output_dir)
    print(f"Report: {md_path}")
    print(f"CSV:    {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

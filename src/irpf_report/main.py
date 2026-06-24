from __future__ import annotations

import argparse
import sys
from pathlib import Path

from irpf_report.calculator import (
    aggregate_by_asset_type,
    aggregate_by_month,
    compute_totals,
    enrich_trades,
)
from irpf_report.report import render_markdown, write_report
from irpf_report.trades import parse_ibkr_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate IRPF BRL report from IBKR trades CSV"
    )
    parser.add_argument(
        "--trades", required=True, type=Path, help="Path to IBKR trades CSV export"
    )
    parser.add_argument(
        "--year", required=True, type=int, help="Calendar year (e.g. 2025)"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Output markdown path"
    )
    args = parser.parse_args()

    if not args.trades.exists():
        print(f"Error: trades file not found: {args.trades}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing trades from {args.trades}...")
    trades = parse_ibkr_csv(args.trades)
    year_trades = [t for t in trades if t.date.year == args.year]
    print(f"Found {len(year_trades)} closed USD trades for {args.year}")

    print("Fetching PTAX rates...")
    enriched = enrich_trades(year_trades)

    missing_ptax = sum(1 for t in enriched if t.ptax_rate is None)
    if missing_ptax:
        print(
            f"Warning: {missing_ptax} trade(s) missing PTAX rate — BRL totals will be incomplete.",
            file=sys.stderr,
        )

    monthly = aggregate_by_month(enriched)
    asset_type_summaries = aggregate_by_asset_type(enriched)
    totals = compute_totals(enriched)

    content = render_markdown(
        year=args.year,
        trades=enriched,
        monthly=monthly,
        asset_type_summaries=asset_type_summaries,
        totals=totals,
    )
    write_report(args.output, content)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()

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
from irpf_report.trades import parse_history_csv, parse_ibkr_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate IRPF BRL report from IBKR trades CSV"
    )
    parser.add_argument(
        "--trades", type=Path, help="IBKR Activity Statement CSV (legacy input)"
    )
    parser.add_argument(
        "--history", type=Path, help="trades_history.csv from ibkr_trades"
    )
    parser.add_argument(
        "--year", required=True, type=int, help="Calendar year (e.g. 2025)"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Output markdown path"
    )
    args = parser.parse_args()

    default_history = Path("data/ibkr/trades_history.csv")
    default_trades = Path(f"data/ibkr/trades_{args.year}.csv")
    if args.history:
        input_path = args.history
        history_mode = True
    elif args.trades:
        input_path = args.trades
        history_mode = False
    elif default_history.exists():
        input_path = default_history
        history_mode = True
        print("Using trades_history.csv (run 'just ibkr-flex-fetch' to refresh)")
    elif default_trades.exists():
        input_path = default_trades
        history_mode = False
        print(f"Using legacy trades CSV: {default_trades}")
    else:
        parser.error(
            "No trade data found. Provide --history or --trades, "
            "or run 'just ibkr-trades-daily' first."
        )

    if not input_path.exists():
        print(f"Error: trades file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing trades from {input_path}...")
    if history_mode:
        year_trades = parse_history_csv(input_path, args.year)
    else:
        trades = parse_ibkr_csv(input_path)
        year_trades = [trade for trade in trades if trade.date.year == args.year]
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

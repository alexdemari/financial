import argparse
from pathlib import Path

from dividend_tracker.config import load_portfolio_config
from dividend_tracker.decision import evaluate_asset
from dividend_tracker.dividend_data import DividendData, fetch_dividend_data
from dividend_tracker.price_ceiling import calculate_price_ceiling
from dividend_tracker.report import write_dividend_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dividend portfolio tracker")
    parser.add_argument(
        "--config",
        default="config/dividend_portfolio.yaml",
        help="Path to dividend portfolio YAML",
    )
    parser.add_argument("--budget", type=float, default=None, help="Daily budget")
    parser.add_argument(
        "--data-dir",
        default="data/stocks",
        help="Kept for backward compatibility — unused",
    )
    parser.add_argument(
        "--output",
        default="reports/dividend_tracker/dividend_daily_report.md",
        help="Markdown report output path",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Use existing local cache only",
    )
    parser.add_argument(
        "--ibkr-positions",
        default=None,
        metavar="PATH",
        help="Path to IBKR positions CSV for USD income projection",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    portfolio_config = load_portfolio_config(args.config)
    decisions = []
    processing_errors = []
    fetched_dividend_data: dict[str, DividendData] = {}

    for asset in portfolio_config.assets:
        try:
            dividend_data = fetch_dividend_data(
                asset.ticker,
                br=asset.market == "BR",
                local_only=args.local_only,
            )
            fetched_dividend_data[asset.ticker.upper()] = dividend_data
            price_ceiling = calculate_price_ceiling(
                asset.ticker,
                min_dy=portfolio_config.resolve_min_dy(asset),
                dividend_data=dividend_data,
                br=asset.market == "BR",
                local_only=args.local_only,
                ceiling_method=portfolio_config.resolve_ceiling_method(asset),
            )
            decisions.append(evaluate_asset(asset, price_ceiling))
        except Exception as exc:
            processing_errors.append(f"{asset.ticker}: {exc}")

    income_projections = None
    usd_cash = None
    if args.ibkr_positions:
        from dividend_tracker.ibkr_enricher import (
            load_ibkr_stk_positions,
            project_annual_income,
        )

        try:
            holdings, usd_cash = load_ibkr_stk_positions(Path(args.ibkr_positions))
            trailing_divs = {
                symbol: data.trailing_annual_dividends
                for symbol, data in fetched_dividend_data.items()
            }
            income_projections = project_annual_income(holdings, trailing_divs)
        except Exception as exc:
            processing_errors.append(f"IBKR enricher: {exc}")

    output_path = write_dividend_report(
        decisions,
        output_path=args.output,
        budget=args.budget,
        processing_errors=processing_errors,
        income_projections=income_projections,
        usd_cash=usd_cash,
    )
    print(f"Relatorio gerado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

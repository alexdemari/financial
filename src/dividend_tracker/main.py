import argparse
from pathlib import Path

from dividend_tracker.config import load_portfolio_config
from dividend_tracker.decision import (
    TechnicalSignalResult,
    evaluate_asset,
    get_technical_signal,
)
from dividend_tracker.dividend_data import fetch_dividend_data
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
        help="Base OHLC data directory used by stock_analyzer",
    )
    parser.add_argument(
        "--output",
        default="reports/dividend_tracker/dividend_daily_report.md",
        help="Markdown report output path",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Use existing local cache and OHLC CSVs only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    portfolio_config = load_portfolio_config(args.config)
    decisions = []
    processing_errors = []

    for asset in portfolio_config.assets:
        try:
            dividend_data = fetch_dividend_data(
                asset.ticker,
                br=asset.market == "BR",
                local_only=args.local_only,
            )
            price_ceiling = calculate_price_ceiling(
                asset.ticker,
                min_dy=portfolio_config.resolve_min_dy(asset),
                dividend_data=dividend_data,
                br=asset.market == "BR",
                local_only=args.local_only,
                ceiling_method=portfolio_config.resolve_ceiling_method(asset),
            )
            primary_signal, confirmation_signal = _get_asset_technical_signals(
                asset,
                data_dir=Path(args.data_dir),
                local_only=args.local_only,
            )
            decisions.append(
                evaluate_asset(
                    asset,
                    price_ceiling,
                    primary_signal,
                    confirmation_signal=confirmation_signal,
                )
            )
        except Exception as exc:
            processing_errors.append(f"{asset.ticker}: {exc}")

    output_path = write_dividend_report(
        decisions,
        output_path=args.output,
        budget=args.budget,
        processing_errors=processing_errors,
        conviction_multiplier=portfolio_config.settings.conviction_multiplier,
    )
    print(f"Relatorio gerado: {output_path}")
    return 0


def _get_asset_technical_signals(
    asset,
    data_dir: Path,
    local_only: bool,
) -> tuple[TechnicalSignalResult, TechnicalSignalResult | None]:
    primary_signal = _call_get_technical_signal(
        asset,
        data_dir=data_dir,
        local_only=local_only,
        model=asset.technical_models.primary,
    )
    confirmation_model = asset.technical_models.confirmation
    if confirmation_model is None:
        return primary_signal, None
    confirmation_signal = _call_get_technical_signal(
        asset, data_dir=data_dir, local_only=local_only, model=confirmation_model
    )
    return primary_signal, confirmation_signal


def _call_get_technical_signal(
    asset,
    data_dir: Path,
    local_only: bool,
    model: str,
) -> TechnicalSignalResult:
    try:
        return get_technical_signal(
            asset, data_dir=data_dir, local_only=local_only, model=model
        )
    except TypeError as exc:
        if "model" not in str(exc):
            raise
        return get_technical_signal(asset, data_dir=data_dir, local_only=local_only)


if __name__ == "__main__":
    raise SystemExit(main())

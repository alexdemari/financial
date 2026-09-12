"""Command-line interface for canonical Binance trade history."""

import argparse
import os
from pathlib import Path

import yaml

from crypto_tracker.binance_client import BinanceReadOnlyClient
from crypto_trades.cost_basis import compute_cost_basis, save_cost_basis
from crypto_trades.parser import parse_export_csv
from crypto_trades.ptax_enricher import enrich_earnings, enrich_trades
from crypto_trades.store import (
    EARN_FIELDS,
    TRADE_FIELDS,
    append_deduplicated,
    load_trades,
)
from crypto_trades.sync import build_known_execution_ids_by_symbol, fetch_new_trades


def main() -> None:
    """Run the requested crypto-history operation."""
    parser = _parser()
    arguments = parser.parse_args()
    if arguments.command == "import":
        trades, earnings = parse_export_csv(arguments.file)
        enrich_trades(trades)
        enrich_earnings(earnings)
        print(
            f"Imported {append_deduplicated(arguments.trades_output, trades, TRADE_FIELDS)} trades and {append_deduplicated(arguments.earn_output, earnings, EARN_FIELDS)} earn records"
        )
    elif arguments.command == "cost-basis":
        save_cost_basis(
            arguments.output, compute_cost_basis(load_trades(arguments.trades))
        )
    else:
        config = (
            yaml.safe_load(arguments.pairs_config.read_text(encoding="utf-8")) or {}
        )
        api_key, api_secret = (
            os.environ["BINANCE_API_KEY"],
            os.environ["BINANCE_API_SECRET"],
        )
        symbols = config.get("pairs", [])
        existing_trades = load_trades(arguments.trades_output)
        trades = fetch_new_trades(
            BinanceReadOnlyClient(api_key, api_secret),
            symbols,
            build_known_execution_ids_by_symbol(existing_trades, symbols),
        )
        enrich_trades(trades)
        print(
            f"Synced {append_deduplicated(arguments.trades_output, trades, TRADE_FIELDS)} trades"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import, sync, and value Binance trade history"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    importing = commands.add_parser("import")
    importing.add_argument("--file", type=Path, required=True)
    importing.add_argument("--trades-output", type=Path, required=True)
    importing.add_argument("--earn-output", type=Path, required=True)
    syncing = commands.add_parser("sync")
    syncing.add_argument("--pairs-config", type=Path, required=True)
    syncing.add_argument("--trades-output", type=Path, required=True)
    cost_basis = commands.add_parser("cost-basis")
    cost_basis.add_argument("--trades", type=Path, required=True)
    cost_basis.add_argument("--output", type=Path, required=True)
    return parser


if __name__ == "__main__":
    main()

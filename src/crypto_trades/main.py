"""Command-line interface for canonical Binance trade history."""

import argparse
import os
from pathlib import Path
from typing import Callable

import yaml

from crypto_tracker.binance_client import BinanceReadOnlyClient
from crypto_trades.cost_basis import compute_cost_basis_with_history, save_cost_basis
from crypto_trades.parser import parse_export_csv
from crypto_trades.ptax_enricher import enrich_earnings, enrich_trades
from crypto_trades.store import (
    EARN_FIELDS,
    TRADE_FIELDS,
    append_deduplicated,
    load_trades,
)
from crypto_trades.sync import build_known_execution_ids_by_symbol, fetch_new_trades

PERSIST_EVERY = 25


def main() -> None:
    """Run the requested crypto-history operation."""
    parser = _parser()
    arguments = parser.parse_args()
    if arguments.command == "import":
        trades, earnings = parse_export_csv(arguments.file)
        print(f"Arquivo lido: {len(trades)} trades e {len(earnings)} registros Earn")
        imported_trades = _enrich_and_persist_incrementally(
            trades,
            arguments.trades_output,
            TRADE_FIELDS,
            enrich_trades,
            "Trades",
        )
        imported_earnings = _enrich_and_persist_incrementally(
            earnings,
            arguments.earn_output,
            EARN_FIELDS,
            enrich_earnings,
            "Earn",
        )
        print(f"Imported {imported_trades} trades and {imported_earnings} earn records")
    elif arguments.command == "cost-basis":
        basis, history = compute_cost_basis_with_history(load_trades(arguments.trades))
        save_cost_basis(arguments.output, basis, history)
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


def _enrich_and_persist_incrementally(
    records: list[object],
    output_path: Path,
    fieldnames: list[str],
    enrich: Callable[..., object],
    label: str,
) -> int:
    """Enrich records with PTAX and persist completed batches for safe resumption."""
    persisted = 0
    added = 0

    def report_progress(completed: int, total: int) -> None:
        nonlocal added, persisted
        print(f"{label} PTAX: {completed}/{total}", flush=True)
        if completed - persisted >= PERSIST_EVERY:
            added += append_deduplicated(
                output_path, records[persisted:completed], fieldnames
            )
            persisted = completed
            print(f"{label}: lote persistido até {persisted}/{total}", flush=True)

    enrich(records, on_progress=report_progress)
    if persisted < len(records):
        added += append_deduplicated(output_path, records[persisted:], fieldnames)
        print(
            f"{label}: lote final persistido ({len(records)}/{len(records)})",
            flush=True,
        )
    return added


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

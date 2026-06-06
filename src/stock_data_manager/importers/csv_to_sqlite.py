"""
CLI script: import all CSV files from a directory into a SQLite database.

Usage:
    PYTHONPATH=src uv run python -m stock_data_manager.importers.csv_to_sqlite \\
        --data-dir data/stocks/1D \\
        --db-path data/financial.db
"""

import argparse
import logging
import sys
from pathlib import Path

from stock_data_manager.repositories.csv_repository import CsvPriceDataRepository
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def import_csv_to_sqlite(data_dir: str, db_path: str) -> None:
    csv_repo = CsvPriceDataRepository(data_dir)
    sqlite_repo = SqlitePriceDataRepository(db_path)

    symbols = csv_repo.list_symbols()

    if not symbols:
        logger.warning("No CSV files found in %s", data_dir)
        return

    logger.info("Found %d symbol(s) in %s", len(symbols), data_dir)

    ok = 0
    skipped = 0
    for symbol in symbols:
        try:
            df = csv_repo.load_symbol(symbol)
            sqlite_repo.save_symbol(symbol, df)
            print(f"  [OK] {symbol}: {len(df)} rows imported")
            ok += 1
        except Exception as exc:
            logger.warning("Skipping %s: %s", symbol, exc)
            skipped += 1

    print(f"\nDone: {ok} imported, {skipped} skipped. DB: {db_path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Import CSV OHLCV files into a SQLite database."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing <SYMBOL>.csv files",
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to the SQLite database file (created if absent)",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: data-dir does not exist: {data_dir}", file=sys.stderr)
        return 1

    import_csv_to_sqlite(str(data_dir), args.db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

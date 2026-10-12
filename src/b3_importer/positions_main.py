"""CLI for immutable B3 custody-position imports."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

from openpyxl.utils.exceptions import InvalidFileException

from b3_importer.positions import parse_positions_xlsx
from b3_importer.positions_store import write_snapshot


def main() -> None:
    """Import one B3 position workbook without printing portfolio data."""
    parser = argparse.ArgumentParser(
        description="Import a B3 custody-position XLSX export"
    )
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/b3/positions"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    arguments = parser.parse_args()
    as_of = arguments.as_of or _as_of_from_filename(arguments.file)
    if as_of is None:
        sys.exit("B3 position import failed: provide --as-of YYYY-MM-DD")
    if as_of > date.today():
        sys.exit("B3 position import failed: --as-of is in the future")
    try:
        snapshot = write_snapshot(
            arguments.output_dir, parse_positions_xlsx(arguments.file, as_of)
        )
    except (OSError, ValueError, zipfile.BadZipFile, InvalidFileException) as error:
        sys.exit(f"B3 position import failed: {error}")
    print(f"B3 position snapshot saved: {snapshot}")


def _as_of_from_filename(path: Path) -> date | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


if __name__ == "__main__":
    main()

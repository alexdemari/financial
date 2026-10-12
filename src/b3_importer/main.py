"""CLI for append-only B3 movement imports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from b3_importer.parser import parse_movements_xlsx
from b3_importer.store import append_movements


def main() -> None:
    """Import one B3 movement workbook and print safe counters."""
    parser = argparse.ArgumentParser(description="Import a B3 movement XLSX export")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/b3/movements_history.csv")
    )
    arguments = parser.parse_args()
    try:
        parsed = parse_movements_xlsx(arguments.file)
    except (OSError, ValueError) as error:
        sys.exit(f"B3 import failed: {error}")
    if parsed.rejected_rows:
        # Nothing is written: occurrence numbering of identical events depends
        # on every valid row being present, so a partial import could dedupe
        # against the wrong occurrence on the next run.
        for rejected in parsed.rejected_rows:
            print(f"Rejected row {rejected.row_number}: {rejected.reason}")
        sys.exit(
            f"B3 import aborted: {len(parsed.rejected_rows)} rejected rows; "
            "fix the export and rerun (nothing was written)"
        )
    summary = append_movements(arguments.output, parsed)
    print(
        "B3 import: "
        f"read={summary.read_count} added={summary.added_count} "
        f"duplicates={summary.duplicate_count} "
        f"ambiguous_collisions={summary.ambiguous_collision_count} "
        f"rejected={len(summary.rejected_rows)}"
    )
    if summary.ambiguous_source_rows:
        print(
            "Review identical events at source rows: "
            + ", ".join(str(row) for row in summary.ambiguous_source_rows)
        )


if __name__ == "__main__":
    main()

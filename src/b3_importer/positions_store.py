"""Write-once persistence for B3 custody snapshots."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from b3_importer.models import B3Position

FIELDS = list(B3Position.__dataclass_fields__)


def write_snapshot(output_dir: Path, positions: list[B3Position]) -> Path:
    """Persist a dated immutable snapshot, reusing an identical prior import."""
    if not positions:
        raise ValueError("B3 position workbook contains no positions")
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = (
        output_dir
        / f"positions_{positions[0].as_of}_{positions[0].source_file_hash[:12]}.csv"
    )
    if snapshot.exists():
        return snapshot
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_dir, prefix=snapshot.name, suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(position.to_dict() for position in positions)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary_name, snapshot)
        except FileExistsError:
            pass
        finally:
            Path(temporary_name).unlink(missing_ok=True)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return snapshot

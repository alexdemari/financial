"""Append-only persistence for canonical B3 movements."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from b3_importer.models import B3Movement, ImportSummary, ParsedMovements

FIELDS = list(B3Movement.__dataclass_fields__)


def append_movements(path: Path, parsed: ParsedMovements) -> ImportSummary:
    """Append events not already present and report ambiguous fingerprints."""
    existing_ids = _existing_ids(path)
    additions = [
        movement
        for movement in parsed.movements
        if movement.event_id not in existing_ids
    ]
    if additions:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(movement.to_dict() for movement in additions)
    collisions = _collision_count(_existing_fingerprints(path), parsed.movements)
    return ImportSummary(
        read_count=len(parsed.movements),
        added_count=len(additions),
        duplicate_count=len(parsed.movements) - len(additions),
        ambiguous_collision_count=collisions,
        rejected_rows=parsed.rejected_rows,
    )


def _existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as input_file:
        return {row["event_id"] for row in csv.DictReader(input_file)}


def _existing_fingerprints(path: Path) -> Counter[str]:
    if not path.exists():
        return Counter()
    with path.open(encoding="utf-8", newline="") as input_file:
        return Counter(
            row["event_id"].rsplit(":", 1)[0] for row in csv.DictReader(input_file)
        )


def _collision_count(existing: Counter[str], movements: list[B3Movement]) -> int:
    incoming = Counter(movement.event_id.rsplit(":", 1)[0] for movement in movements)
    return sum(
        1
        for fingerprint, count in incoming.items()
        if count > 1 or existing[fingerprint] > 1
    )

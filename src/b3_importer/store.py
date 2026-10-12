"""Append-only persistence for canonical B3 movements."""

from __future__ import annotations

import csv
import fcntl
import os
import shutil
import tempfile
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from b3_importer.models import B3Movement, ImportSummary, ParsedMovements

FIELDS = list(B3Movement.__dataclass_fields__)


def append_movements(path: Path, parsed: ParsedMovements) -> ImportSummary:
    """Append events not already present and report ambiguous fingerprints.

    The history is rewritten through a temp file and ``os.replace`` under an
    exclusive lock, so a crash never leaves a partial row and concurrent
    imports cannot both append the same events.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(path):
        existing_ids, existing_fingerprints = _read_existing(path)
        additions = [
            movement
            for movement in parsed.movements
            if movement.event_id not in existing_ids
        ]
        if additions:
            _write_with_additions(path, additions)
    return ImportSummary(
        read_count=len(parsed.movements),
        added_count=len(additions),
        duplicate_count=len(parsed.movements) - len(additions),
        ambiguous_source_rows=_ambiguous_source_rows(existing_fingerprints, additions),
        rejected_rows=parsed.rejected_rows,
    )


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    with path.with_name(path.name + ".lock").open("a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _write_with_additions(path: Path, additions: list[B3Movement]) -> None:
    has_content = path.exists() and path.stat().st_size > 0
    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as output:
            if has_content:
                with path.open(encoding="utf-8", newline="") as current:
                    shutil.copyfileobj(current, output)
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            if not has_content:
                writer.writeheader()
            writer.writerows(movement.to_dict() for movement in additions)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _read_existing(path: Path) -> tuple[set[str], Counter[str]]:
    if not path.exists():
        return set(), Counter()
    with path.open(encoding="utf-8", newline="") as input_file:
        event_ids = [row["event_id"] for row in csv.DictReader(input_file)]
    return set(event_ids), Counter(_fingerprint(event_id) for event_id in event_ids)


def _fingerprint(event_id: str) -> str:
    return event_id.rsplit(":", 1)[0]


def _ambiguous_source_rows(
    existing: Counter[str], additions: list[B3Movement]
) -> list[int]:
    """Source rows of added events sharing a fingerprint with any other event."""
    added = Counter(_fingerprint(movement.event_id) for movement in additions)
    return [
        movement.source_row_number
        for movement in additions
        if existing[_fingerprint(movement.event_id)]
        + added[_fingerprint(movement.event_id)]
        > 1
    ]

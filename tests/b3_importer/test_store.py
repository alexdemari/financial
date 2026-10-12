from pathlib import Path

from b3_importer.models import B3Movement, ParsedMovements
from b3_importer.store import append_movements


def _movement(event_id: str) -> B3Movement:
    return B3Movement(
        event_id=event_id,
        event_date="2026-10-11",
        direction="entrada",
        movement_type="Compra",
        product="TAEE11",
        institution="BTG",
        quantity=10.0,
        unit_price_brl=40.5,
        operation_value_brl=405.0,
        source_file_hash="source",
        source_row_number=2,
        imported_at="2026-10-11T12:00:00+00:00",
    )


def test_store_is_idempotent_for_the_same_import(tmp_path: Path):
    output = tmp_path / "movements.csv"
    parsed = ParsedMovements([_movement("event:1")], [])

    first = append_movements(output, parsed)
    second = append_movements(output, parsed)

    assert (first.added_count, first.duplicate_count) == (1, 0)
    assert (second.added_count, second.duplicate_count) == (0, 1)
    assert len(output.read_text().splitlines()) == 2


def test_store_preserves_same_fingerprint_multiplicity_and_reports_collision(
    tmp_path: Path,
):
    output = tmp_path / "movements.csv"
    parsed = ParsedMovements([_movement("event:1"), _movement("event:2")], [])

    summary = append_movements(output, parsed)

    assert summary.added_count == 2
    assert summary.ambiguous_collision_count == 2
    assert len(output.read_text().splitlines()) == 3


def test_store_reports_ambiguous_rows_only_for_added_events(tmp_path: Path):
    output = tmp_path / "movements.csv"
    parsed = ParsedMovements([_movement("event:1"), _movement("event:2")], [])

    first = append_movements(output, parsed)
    second = append_movements(output, parsed)

    assert first.ambiguous_source_rows == [2, 2]
    assert second.added_count == 0
    assert second.ambiguous_source_rows == []


def test_store_leaves_no_temp_files(tmp_path: Path):
    append_movements(
        tmp_path / "movements.csv", ParsedMovements([_movement("a:1")], [])
    )

    assert not list(tmp_path.glob("*.tmp"))

"""Canonical B3 movement records."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class B3Movement:
    """One normalized movement from the B3 investor statement."""

    event_id: str
    event_date: str
    direction: str
    movement_type: str
    product: str
    institution: str
    quantity: float | None
    unit_price_brl: float | None
    operation_value_brl: float | None
    source_file_hash: str
    source_row_number: int
    imported_at: str

    def to_dict(self) -> dict[str, object]:
        """Return the stable CSV representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RejectedRow:
    """A source row that could not be safely normalized."""

    row_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class ParsedMovements:
    """The valid and invalid rows read from one statement."""

    movements: list[B3Movement]
    rejected_rows: list[RejectedRow]


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Safe-to-display counters from one append-only import."""

    read_count: int
    added_count: int
    duplicate_count: int
    ambiguous_collision_count: int
    rejected_rows: list[RejectedRow]

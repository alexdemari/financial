from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

_WEEKDAY_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_IMPACT_LABEL = {"high": "HIGH", "medium": "MED", "low": "LOW"}


@dataclass(frozen=True)
class MacroEvent:
    date: date
    event: str
    impact: str  # high | medium | low

    @property
    def weekday_pt(self) -> str:
        return _WEEKDAY_PT[self.date.weekday()]

    @property
    def impact_label(self) -> str:
        return _IMPACT_LABEL.get(self.impact, self.impact.upper())


def load_macro_calendar(path: Path | str) -> list[MacroEvent]:
    """Load events from YAML. Returns [] if file is missing."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    events: list[MacroEvent] = []
    for item in data.get("events", []):
        raw_date = item["date"]
        if isinstance(raw_date, str):
            raw_date = date.fromisoformat(raw_date)
        events.append(
            MacroEvent(
                date=raw_date,
                event=item["event"],
                impact=item.get("impact", "medium").lower(),
            )
        )
    return sorted(events, key=lambda e: e.date)


def upcoming_events(
    path: Path | str,
    days_ahead: int = 14,
    reference_date: date | None = None,
) -> list[MacroEvent]:
    """Return events from reference_date through reference_date + days_ahead (inclusive)."""
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()
    return [
        e
        for e in load_macro_calendar(path)
        if 0 <= (e.date - reference_date).days <= days_ahead
    ]

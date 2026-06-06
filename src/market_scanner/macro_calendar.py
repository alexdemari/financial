from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

_WEEKDAY_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_IMPACT_LABEL = {"high": "HIGH", "medium": "MED", "low": "LOW"}
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
_TIMEOUT = 6  # seconds per request
_MAX_WORKERS = 5  # parallel day fetches

# (substring_to_match, display_name, impact) — first match wins per event name
_KEY_EVENTS: list[tuple[str, str, str]] = [
    ("Nonfarm Payrolls", "Non-Farm Payroll", "high"),
    ("Fed Interest Rate Decision", "FOMC - Decisão de Juros", "high"),
    ("Core CPI", "CPI Core", "high"),
    ("CPI", "CPI", "high"),
    ("Core PCE Price Index", "PCE Core", "high"),
    ("PCE price index", "PCE", "high"),
    ("PCE Prices", "PCE", "high"),
    ("PPI", "PPI", "medium"),
    ("Gross Domestic Product", "PIB (GDP)", "high"),
    ("JOLTS Job Openings", "JOLTS - Vagas", "medium"),
    ("Retail Sales", "Retail Sales", "medium"),
    ("Consumer Confidence", "Consumer Confidence", "medium"),
    ("ISM Manufacturing", "ISM Manufacturing", "medium"),
    ("ISM Services", "ISM Services", "medium"),
]


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


def _fetch_day(d: date) -> list[MacroEvent]:
    url = f"https://api.nasdaq.com/api/calendar/economicevents?date={d}&daterange=day"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        data = json.loads(r.read())
    rows = data.get("data", {}).get("rows", []) or []

    seen: set[str] = set()
    events: list[MacroEvent] = []
    for row in rows:
        if row.get("country") != "United States":
            continue
        name = row.get("eventName", "")
        for pattern, display, impact in _KEY_EVENTS:
            if pattern.lower() in name.lower() and display not in seen:
                seen.add(display)
                events.append(MacroEvent(date=d, event=display, impact=impact))
                break
    return events


def fetch_macro_events(
    days_ahead: int = 14,
    reference_date: date | None = None,
) -> list[MacroEvent] | None:
    """Fetch upcoming US macro events from Nasdaq Economic Calendar.

    Returns sorted list of events, or None if the API is completely unreachable.
    Weekends are skipped. Individual day failures are silently ignored.
    Requests run in parallel to minimise latency (~1-2s for a 14-day window).
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()

    weekdays = [
        reference_date + timedelta(days=offset)
        for offset in range(days_ahead + 1)
        if (reference_date + timedelta(days=offset)).weekday() < 5
    ]

    events: list[MacroEvent] = []
    api_reachable = False

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_fetch_day, d): d for d in weekdays}
        for future in as_completed(futures):
            try:
                events.extend(future.result())
                api_reachable = True
            except Exception:
                pass

    if not api_reachable:
        return None
    return sorted(events, key=lambda e: e.date)

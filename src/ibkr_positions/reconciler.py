"""Reconcile options_tracker.csv against a live IBKR snapshot CSV.

Read-only: never modifies either input file.

Match key: (underlying, option_type, strike, expiration) — ISO date, float strike.
Tracker rows with a non-empty Close Date are considered closed and excluded.
Quantities are compared as signed values: tracker C/V field determines sign
(V=short→negative, C=long→positive); live snapshot quantity is already signed.
Multiple tracker rows for the same contract (separate lots) are summed before
comparison to match IBKR's aggregate position reporting.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd

MatchKey = tuple[str, str, float, str]  # (underlying, option_type, strike, expiration)


@dataclass
class ReconciliationResult:
    live_only: list[dict] = field(default_factory=list)
    tracker_only: list[dict] = field(default_factory=list)
    quantity_mismatch: list[dict] = field(default_factory=list)
    in_sync: bool = True


def _parse_decimal(value: object) -> float:
    """Convert comma-decimal string or numeric to float."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "."))


def _to_iso_date(value: str) -> str:
    """Normalise DD/MM/YYYY or YYYY-MM-DD to YYYY-MM-DD."""
    value = str(value).strip()
    if "/" in value:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    return value


def _load_tracker(path: Path | StringIO) -> dict[MatchKey, float]:
    """Return {match_key: signed_quantity} for open tracker rows, summed across lots."""
    df = pd.read_csv(path, sep=";", dtype=str)
    df.columns = df.columns.str.strip()

    open_rows = df[df["Close Date"].fillna("").str.strip() == ""]

    result: dict[MatchKey, float] = {}
    for _, row in open_rows.iterrows():
        key: MatchKey = (
            str(row["Asset"]).strip().upper(),
            str(row["Type"]).strip().upper(),
            _parse_decimal(row["Strike"]),
            _to_iso_date(row["Due date"]),
        )
        direction = -1.0 if str(row["C/V"]).strip().upper() == "V" else 1.0
        signed_qty = direction * abs(_parse_decimal(row["Qty (Contracts)"]))
        result[key] = result.get(key, 0.0) + signed_qty
    return result


def _load_live(path: Path | StringIO) -> dict[MatchKey, float]:
    """Return {match_key: signed_quantity} for live snapshot rows, summed across lots."""
    df = pd.read_csv(path, sep=";", dtype=str)
    df.columns = df.columns.str.strip()

    result: dict[MatchKey, float] = {}
    for _, row in df.iterrows():
        key: MatchKey = (
            str(row["underlying"]).strip().upper(),
            str(row["option_type"]).strip().upper(),
            _parse_decimal(row["strike"]),
            _to_iso_date(row["expiration"]),
        )
        result[key] = result.get(key, 0.0) + _parse_decimal(row["quantity"])
    return result


def reconcile(
    live_csv: Path | StringIO,
    tracker_csv: Path | StringIO,
) -> ReconciliationResult:
    """Diff live snapshot against open tracker positions."""
    live = _load_live(live_csv)
    tracker = _load_tracker(tracker_csv)

    live_keys = set(live)
    tracker_keys = set(tracker)

    live_only = [
        {
            "underlying": k[0],
            "option_type": k[1],
            "strike": k[2],
            "expiration": k[3],
            "quantity": live[k],
        }
        for k in live_keys - tracker_keys
    ]
    tracker_only = [
        {
            "underlying": k[0],
            "option_type": k[1],
            "strike": k[2],
            "expiration": k[3],
            "quantity": tracker[k],
        }
        for k in tracker_keys - live_keys
    ]
    quantity_mismatch = [
        {
            "underlying": k[0],
            "option_type": k[1],
            "strike": k[2],
            "expiration": k[3],
            "tracker_qty": tracker[k],
            "live_qty": live[k],
        }
        for k in live_keys & tracker_keys
        if live[k] != tracker[k]
    ]

    in_sync = not (live_only or tracker_only or quantity_mismatch)
    return ReconciliationResult(
        live_only=live_only,
        tracker_only=tracker_only,
        quantity_mismatch=quantity_mismatch,
        in_sync=in_sync,
    )


def format_report(result: ReconciliationResult) -> str:
    if result.in_sync:
        return "✓ options_tracker.csv is in sync with IBKR."

    lines: list[str] = []

    if result.live_only:
        lines.append("── LIVE ONLY (add to tracker) " + "─" * 40)
        for item in result.live_only:
            lines.append(
                f"  {item['underlying']} {item['option_type']} ${item['strike']:.2f}"
                f" exp {item['expiration']}  qty={item['quantity']:.0f}"
            )

    if result.tracker_only:
        lines.append("── TRACKER ONLY (mark closed or verify) " + "─" * 30)
        for item in result.tracker_only:
            lines.append(
                f"  {item['underlying']} {item['option_type']} ${item['strike']:.2f}"
                f" exp {item['expiration']}  qty={item['quantity']:.0f}"
            )

    if result.quantity_mismatch:
        lines.append("── QUANTITY MISMATCH " + "─" * 49)
        for item in result.quantity_mismatch:
            lines.append(
                f"  {item['underlying']} {item['option_type']} ${item['strike']:.2f}"
                f" exp {item['expiration']}:"
                f"  tracker={item['tracker_qty']:.0f} | live={item['live_qty']:.0f}"
            )

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reconcile options_tracker.csv vs live IBKR snapshot."
    )
    p.add_argument(
        "--live", required=True, type=Path, help="Path to options_tracker_live.csv"
    )
    p.add_argument(
        "--tracker", required=True, type=Path, help="Path to options_tracker.csv"
    )
    p.add_argument(
        "--output", type=Path, default=None, help="Optional output .md file path"
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    result = reconcile(args.live, args.tracker)
    report = format_report(result)
    print(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

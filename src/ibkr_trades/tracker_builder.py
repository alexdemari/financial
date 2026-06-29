from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from market_scanner.options_tracker_schema import OPTIONS_TRACKER_COLUMNS

# Additive columns appended after the canonical 26 — exit_monitor ignores them
_EXTRA_COLUMNS = ("trade_id", "roll_id", "strategy")
_ALL_COLUMNS = tuple(OPTIONS_TRACKER_COLUMNS) + _EXTRA_COLUMNS

_MATCH_KEY = ["underlying", "option_type", "strike", "expiration"]


def _fmt_float(value: float | None, decimal_places: int = 2) -> str:
    if value is None:
        return ""
    return f"{value:.{decimal_places}f}"


def _fmt_date(d: date | None) -> str:
    if d is None:
        return ""
    return d.isoformat()


def _dte(expiration: str | None) -> str:
    if not expiration:
        return ""
    try:
        exp_date = date.fromisoformat(expiration[:10])
        return str((exp_date - date.today()).days)
    except ValueError:
        return ""


def build_options_tracker(
    history_path: Path,
    tracker_path: Path,
    backup_dir: Path | None = None,
) -> int:
    """Derive options_tracker.csv from trades_history.csv.

    Net quantity per contract: sum(quantity). Non-zero net = open position.
    Archives any existing tracker to backup_dir on first run (no backup present).
    Returns number of open legs written.
    """
    _maybe_archive(tracker_path, backup_dir)

    df = pd.read_csv(history_path, dtype={"trade_id": str, "roll_id": str})
    opts = df[df["asset_type"] == "OPT"].copy()

    if opts.empty:
        _write_empty(tracker_path)
        return 0

    # Net position per contract: positive=long, negative=short
    net = opts.groupby(_MATCH_KEY, dropna=False)["quantity"].sum().reset_index()
    net.rename(columns={"quantity": "net_qty"}, inplace=True)
    open_legs = net[net["net_qty"].abs() > 0.001].copy()

    if open_legs.empty:
        _write_empty(tracker_path)
        return 0

    # Most recent opening trade per contract for metadata
    opening = opts[opts["open_close"].str.contains("O", na=False)].copy()
    latest_open = (
        opening.sort_values("datetime")
        .groupby(_MATCH_KEY, dropna=False)
        .last()
        .reset_index()
    )

    merged = open_legs.merge(latest_open, on=_MATCH_KEY, how="left")

    rows: list[dict] = []
    for _, r in merged.iterrows():
        net_qty = r["net_qty"]
        open_direction = "V" if net_qty < 0 else "C"
        abs_contracts = abs(net_qty)
        open_qty = abs(r.get("quantity", net_qty)) or 1
        premium_per_contract = abs(r.get("proceeds", 0)) / open_qty

        entry_date_val = r.get("date", "")
        try:
            entry_date_str = _fmt_date(date.fromisoformat(str(entry_date_val)[:10]))
        except (ValueError, TypeError):
            entry_date_str = str(entry_date_val)

        expiration = str(r.get("expiration", "") or "")

        row: dict = {
            "entry_date": entry_date_str,
            "platform": "IBKR",
            "currency": str(r.get("currency", "USD") or "USD"),
            "symbol": str(r.get("underlying", "") or ""),
            "underlying": str(r.get("underlying", "") or ""),
            "option_type": str(r.get("option_type", "") or ""),
            "open_direction": open_direction,
            "expiration": expiration,
            "strike": _fmt_float(r.get("strike")),
            "premium_received": _fmt_float(premium_per_contract),
            "quantity": str(int(abs_contracts))
            if abs_contracts == int(abs_contracts)
            else str(abs_contracts),
            "current_value": "",
            "unrealized_pnl": "",
            "delta": "",
            "iv": "",
            "dte": _dte(expiration),
            "collateral": "",
            "close_action": "",
            "close_date": "",
            "close_quantity": "",
            "close_value": "",
            "close_costs": "",
            "result": "",
            "size": "0",
            "close_description": "",
            "signal_source": "ibkr_trades",
            # additive
            "trade_id": str(r.get("trade_id", "") or ""),
            "roll_id": str(r.get("roll_id", "") or ""),
            "strategy": str(r.get("strategy", "") or ""),
        }
        rows.append(row)

    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    with tracker_path.open("w", encoding="utf-8") as f:
        f.write(";".join(_ALL_COLUMNS) + "\n")
        for row in rows:
            f.write(";".join(row[col] for col in _ALL_COLUMNS) + "\n")

    return len(rows)


def _write_empty(tracker_path: Path) -> None:
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    tracker_path.write_text(";".join(_ALL_COLUMNS) + "\n", encoding="utf-8")


def _maybe_archive(tracker_path: Path, backup_dir: Path | None) -> None:
    """Archive existing tracker on first run (when no backup exists yet)."""
    if not tracker_path.exists():
        return
    if backup_dir is None:
        backup_dir = tracker_path.parent
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Only archive once — skip if any backup already exists
    existing_backups = list(backup_dir.glob("options_tracker_manual_backup_*.csv"))
    if existing_backups:
        return
    backup_name = f"options_tracker_manual_backup_{date.today().isoformat()}.csv"
    shutil.copy2(tracker_path, backup_dir / backup_name)

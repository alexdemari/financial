from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ibkr_trades.option_types import normalize_option_type
from market_scanner.options_tracker_schema import OPTIONS_TRACKER_COLUMNS

# Additive columns appended after the canonical 26 — exit_monitor ignores them
_EXTRA_COLUMNS = ("trade_id", "roll_id", "strategy")
_ALL_COLUMNS = tuple(OPTIONS_TRACKER_COLUMNS) + _EXTRA_COLUMNS

_MATCH_KEY = ["underlying", "option_type", "strike", "expiration"]
_EQUIVALENT_EXECUTION_KEY = [
    "date",
    "underlying",
    "option_type",
    "strike",
    "expiration",
    "quantity",
    "price",
]


def _fmt_float(value: float | None, decimal_places: int = 2) -> str:
    if value is None or pd.isna(value):
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


def _clean_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    value_str = str(value)
    return "" if value_str.lower() == "nan" else value_str


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _valid_trade_id_mask(series: pd.Series) -> pd.Series:
    trade_ids = series.astype("string").str.strip()
    return trade_ids.notna() & ~trade_ids.str.lower().isin(["", "nan", "none", "<na>"])


def _prepare_options_history(df: pd.DataFrame) -> pd.DataFrame:
    opts = df[df["asset_type"] == "OPT"].copy()
    if opts.empty:
        return opts

    opts = opts[_valid_trade_id_mask(opts["trade_id"])].copy()
    if opts.empty:
        return opts

    opts["option_type"] = opts["option_type"].map(normalize_option_type).fillna("")
    expiration_dates = pd.to_datetime(opts["expiration"], errors="coerce").dt.date
    opts = opts[expiration_dates.notna() & (expiration_dates >= date.today())].copy()
    if opts.empty:
        return opts

    opts["_source_priority"] = opts["source"].eq("flex").astype(int)

    # Daily Flex plus API sync can record the same execution with different
    # trade IDs. Prefer Flex because it has open_close, commission, and P&L.
    opts = opts.sort_values(["_source_priority", "datetime"], ascending=[False, True])
    opts = opts.drop_duplicates(_EQUIVALENT_EXECUTION_KEY, keep="first")
    return opts.drop(columns=["_source_priority"])


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
    opts = _prepare_options_history(df)

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

    # Most recent opening trade per contract for metadata; fall back to the
    # latest trade when legacy API rows do not include open_close.
    opts["_metadata_priority"] = (
        opts["open_close"].str.contains("O", na=False).astype(int)
    )
    latest_metadata = (
        opts.sort_values(["_metadata_priority", "datetime"])
        .groupby(_MATCH_KEY, dropna=False)
        .last()
        .reset_index()
        .drop(columns=["_metadata_priority"])
    )

    merged = open_legs.merge(latest_metadata, on=_MATCH_KEY, how="left")

    rows: list[dict] = []
    for _, r in merged.iterrows():
        net_qty = r["net_qty"]
        open_direction = "V" if net_qty < 0 else "C"
        abs_contracts = abs(net_qty)
        open_qty = abs(_to_float(r.get("quantity"), net_qty)) or 1
        premium_per_contract = abs(_to_float(r.get("proceeds"))) / open_qty

        entry_date_val = r.get("date", "")
        try:
            entry_date_str = _fmt_date(date.fromisoformat(str(entry_date_val)[:10]))
        except (ValueError, TypeError):
            entry_date_str = _clean_str(entry_date_val)

        expiration = _clean_str(r.get("expiration"))

        row: dict = {
            "entry_date": entry_date_str,
            "platform": "IBKR",
            "currency": _clean_str(r.get("currency")) or "USD",
            "symbol": _clean_str(r.get("underlying")),
            "underlying": _clean_str(r.get("underlying")),
            "option_type": _clean_str(r.get("option_type")),
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
            "trade_id": _clean_str(r.get("trade_id")),
            "roll_id": _clean_str(r.get("roll_id")),
            "strategy": _clean_str(r.get("strategy")),
        }
        rows.append(row)

    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    with tracker_path.open("w", encoding="utf-8") as f:
        f.write(";".join(_ALL_COLUMNS) + "\n")
        for row in rows:
            f.write(";".join(_clean_str(row[col]) for col in _ALL_COLUMNS) + "\n")

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

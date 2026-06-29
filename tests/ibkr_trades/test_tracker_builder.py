"""Tests for tracker_builder.py"""

from pathlib import Path

import pandas as pd

from ibkr_trades.tracker_builder import build_options_tracker

_HISTORY_COLS = [
    "trade_id",
    "date",
    "datetime",
    "symbol",
    "underlying",
    "asset_type",
    "option_type",
    "strike",
    "expiration",
    "quantity",
    "price",
    "proceeds",
    "commission",
    "pnl_realized",
    "currency",
    "open_close",
    "source",
    "roll_id",
    "strategy",
]


def _write_history(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows, columns=_HISTORY_COLS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _base_row(**kwargs) -> dict:
    defaults = dict(
        trade_id="TID-001",
        date="2026-06-10",
        datetime="2026-06-10T09:00:00",
        symbol="PEP   260717P00140000",
        underlying="PEP",
        asset_type="OPT",
        option_type="PUT",
        strike=140.0,
        expiration="2026-07-17",
        quantity=-1.0,
        price=2.86,
        proceeds=286.0,
        commission=-0.71,
        pnl_realized=None,
        currency="USD",
        open_close="O",
        source="flex",
        roll_id=None,
        strategy="csp",
    )
    defaults.update(kwargs)
    return defaults


def test_tracker_builder_shows_only_open_legs(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    # open -1, close +1 → net 0 → not in tracker
    _write_history(
        history,
        [
            _base_row(trade_id="T1", quantity=-1.0, open_close="O"),
            _base_row(trade_id="T2", quantity=1.0, open_close="C"),
        ],
    )
    n = build_options_tracker(history, tracker)
    assert n == 0
    content = tracker.read_text()
    data_lines = [line for line in content.splitlines() if line.strip()][1:]
    assert data_lines == []


def test_tracker_builder_correct_net_qty_for_partial_close(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    # open -12, close +6 → net -6 → tracker shows qty=6
    _write_history(
        history,
        [
            _base_row(trade_id="T1", quantity=-12.0, proceeds=3432.0, open_close="O"),
            _base_row(trade_id="T2", quantity=6.0, proceeds=-1716.0, open_close="C"),
        ],
    )
    n = build_options_tracker(history, tracker)
    assert n == 1
    lines = tracker.read_text().splitlines()
    header = lines[0].split(";")
    row = lines[1].split(";")
    qty_idx = header.index("quantity")
    assert row[qty_idx] == "6"


def test_tracker_builder_archives_existing_manual_tracker(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    backup_dir = tmp_path / "backups"

    # Pre-existing manual tracker
    tracker.write_text("manual content\n", encoding="utf-8")

    _write_history(history, [_base_row()])
    build_options_tracker(history, tracker, backup_dir=backup_dir)

    backups = list(backup_dir.glob("options_tracker_manual_backup_*.csv"))
    assert len(backups) == 1
    assert backups[0].read_text() == "manual content\n"


def test_tracker_builder_no_double_archive(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    backup_dir = tmp_path / "backups"

    tracker.write_text("manual content\n", encoding="utf-8")
    _write_history(history, [_base_row()])

    build_options_tracker(history, tracker, backup_dir=backup_dir)
    build_options_tracker(history, tracker, backup_dir=backup_dir)  # second run

    backups = list(backup_dir.glob("options_tracker_manual_backup_*.csv"))
    assert len(backups) == 1  # not archived again


def test_tracker_builder_output_semicolon_delimited(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    _write_history(history, [_base_row()])
    build_options_tracker(history, tracker)
    first_line = tracker.read_text().splitlines()[0]
    assert ";" in first_line
    assert "," not in first_line.split(";")[0]  # no comma in first field


def test_tracker_builder_open_direction_short(tmp_path: Path):
    history = tmp_path / "trades_history.csv"
    tracker = tmp_path / "options_tracker.csv"
    _write_history(history, [_base_row(quantity=-1.0)])
    build_options_tracker(history, tracker)
    lines = tracker.read_text().splitlines()
    header = lines[0].split(";")
    row = lines[1].split(";")
    dir_idx = header.index("open_direction")
    assert row[dir_idx] == "V"

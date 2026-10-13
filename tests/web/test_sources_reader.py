import os
import time
from datetime import date, timedelta

import pytest

from web.readers import b3_positions_reader, sources_reader


@pytest.fixture
def isolated_sources(monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    for name in (
        "SNAPSHOT_PATH",
        "CASH_CONFIG_PATH",
        "CREDIT_CONFIG_PATH",
        "SCAN_PATH",
        "DIVIDEND_REPORT_PATH",
        "BTG_OPCOES_POS",
        "BTG_GERAL_POS",
    ):
        monkeypatch.setattr(sources_reader, name, missing / name)
    monkeypatch.setattr(sources_reader, "latest_ibkr_csv", lambda: None)
    monkeypatch.setattr(sources_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(b3_positions_reader, "B3_POSITIONS_DIR", tmp_path / "b3")
    monkeypatch.setattr(
        b3_positions_reader, "B3_RECONCILIATION_REPORT", tmp_path / "report.md"
    )
    return tmp_path


def _by_name(sources):
    return {source["name"]: source for source in sources}


def test_missing_sources_report_no_data_with_next_step(isolated_sources):
    sources = _by_name(sources_reader.read_sources())

    assert {source["status"] for source in sources.values()} == {"no_data"}
    assert sources["B3"]["hint"] == "Run: just b3-positions-import"
    assert sources["Scanner"]["hint"] == "Run: just daily"


def test_old_file_is_stale_and_fresh_file_is_ok(isolated_sources):
    path = isolated_sources / "scan.csv"
    path.write_text("x")
    fresh = sources_reader._file_source("Scanner", path, "hint", stale_hours=25)
    old_time = time.time() - 26 * 3600
    os.utime(path, (old_time, old_time))
    stale = sources_reader._file_source("Scanner", path, "hint", stale_hours=25)

    assert fresh["status"] == "ok" and fresh["hint"] is None
    assert stale["status"] == "stale" and stale["hint"] == "hint"


def test_manual_sources_are_estimated_not_alarming(isolated_sources):
    path = isolated_sources / "cash.yaml"
    path.write_text("x")

    source = sources_reader._file_source("Caixa", path, "hint", status="estimated")

    assert source["status"] == "estimated"


def test_old_ibkr_history_is_stale(monkeypatch, isolated_sources):
    class Snapshot:
        as_of = (date.today() - timedelta(days=30)).isoformat()
        last_updated = "2026-01-01T00:00:00+00:00"

    monkeypatch.setattr(sources_reader, "read_account_snapshot", lambda: Snapshot())

    source = sources_reader._history_source()

    assert source["status"] == "stale"
    assert source["hint"] == "Run: just ibkr-positions"


def test_b3_stale_snapshot_points_to_import_and_unreconciled_is_partial(
    isolated_sources,
):
    directory = b3_positions_reader.B3_POSITIONS_DIR
    directory.mkdir()
    today = date.today().isoformat()
    (directory / "positions_2020-01-01_aaa.csv").write_text("x")
    assert sources_reader._b3_source()["status"] == "stale"
    assert sources_reader._b3_source()["hint"] == "Run: just b3-positions-import"

    (directory / f"positions_{today}_bbb.csv").write_text("x")
    source = sources_reader._b3_source()
    assert source["status"] == "partial"
    assert source["hint"] == "Run: just b3-reconcile"

    b3_positions_reader.B3_RECONCILIATION_REPORT.write_text(
        f"Snapshot: `positions_{today}_bbb.csv`\n"
        "| missing_btg | 0 |\n| excess_btg | 0 |\n| quantity_mismatch | 0 |\n"
    )
    assert sources_reader._b3_source()["status"] == "ok"


def test_one_failing_source_does_not_hide_the_others(monkeypatch, isolated_sources):
    def broken():
        raise ValueError("corrupt")

    monkeypatch.setattr(sources_reader, "read_account_snapshot", broken)

    sources = _by_name(sources_reader.read_sources())

    assert sources["Histórico IBKR"]["status"] == "partial"
    assert sources["B3"]["status"] == "no_data"
    assert len(sources) == 9


def test_exit_options_counted_and_failure_isolated(monkeypatch):
    class Position:
        def __init__(self, asset_type, risk_status):
            self.asset_type = asset_type
            self.risk_status = risk_status

    monkeypatch.setattr(
        sources_reader,
        "read_positions",
        lambda: [
            Position("OPT", "EXIT"),
            Position("OPT", "HOLD"),
            Position("STK", None),
        ],
    )
    assert sources_reader.read_alerts() == {"exit_options": 1}

    def broken():
        raise OSError("gone")

    monkeypatch.setattr(sources_reader, "read_positions", broken)
    assert sources_reader.read_alerts() == {"exit_options": None}

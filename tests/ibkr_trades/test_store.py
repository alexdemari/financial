"""Tests for store.py"""

from datetime import date
from pathlib import Path


from ibkr_trades.models import TradeRecord
from ibkr_trades.store import append_trades, last_sync_date, load_history


def _make_record(trade_id: str, trade_date: date = date(2026, 6, 10)) -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        date=trade_date,
        datetime=f"{trade_date.isoformat()}T09:00:00",
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
    )


def test_store_append_deduplicates_by_trade_id(tmp_path: Path):
    path = tmp_path / "history.csv"
    record = _make_record("TID-001")
    append_trades([record], path)
    append_trades([record], path)  # duplicate
    df = load_history(path)
    assert len(df) == 1


def test_store_append_returns_added_and_skipped_counts(tmp_path: Path):
    path = tmp_path / "history.csv"
    r1 = _make_record("TID-001")
    r2 = _make_record("TID-002")
    r3 = _make_record("TID-003")
    append_trades([r1, r2, r3], path)

    r4 = _make_record("TID-004")
    r5 = _make_record("TID-005")
    added, skipped = append_trades([r1, r2, r4, r5], path)
    assert added == 2
    assert skipped == 2


def test_store_last_sync_date_returns_most_recent_date(tmp_path: Path):
    path = tmp_path / "history.csv"
    append_trades([_make_record("TID-001", date(2026, 6, 1))], path)
    append_trades([_make_record("TID-002", date(2026, 6, 20))], path)
    result = last_sync_date(path)
    assert result == date(2026, 6, 20)


def test_store_last_sync_date_none_when_empty(tmp_path: Path):
    path = tmp_path / "history.csv"
    assert last_sync_date(path) is None


def test_store_append_to_empty_path(tmp_path: Path):
    path = tmp_path / "sub" / "history.csv"
    added, skipped = append_trades([_make_record("TID-001")], path)
    assert added == 1
    assert skipped == 0
    assert path.exists()


def test_store_deduplicates_within_incoming_batch(tmp_path: Path):
    # Two copies of same trade_id in a single batch → only one row written
    path = tmp_path / "history.csv"
    r = _make_record("TID-DUP")
    added, skipped = append_trades([r, r], path)
    assert added == 1
    df = load_history(path)
    assert len(df) == 1

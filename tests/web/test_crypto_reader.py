from datetime import UTC, datetime

from crypto_tracker.snapshot import CryptoSnapshot
from web.readers import crypto_reader


def test_returns_none_when_no_snapshot(monkeypatch):
    monkeypatch.setattr(crypto_reader, "load_last_snapshot", lambda: None)

    assert crypto_reader.read_crypto_snapshot() is None


def test_returns_snapshot_when_file_exists(monkeypatch):
    expected = CryptoSnapshot([], 10, 50, 5, datetime.now(UTC).isoformat())
    monkeypatch.setattr(crypto_reader, "load_last_snapshot", lambda: expected)

    assert crypto_reader.read_crypto_snapshot() == expected


def test_stale_flag_when_old_snapshot(monkeypatch):
    expected = CryptoSnapshot([], 10, 50, 5, "2020-01-01T00:00:00+00:00")
    monkeypatch.setattr(crypto_reader, "load_last_snapshot", lambda: expected)

    assert crypto_reader.read_crypto_snapshot().stale is True

import json
from datetime import UTC, datetime, timedelta

import pytest

from crypto_tracker import snapshot


def _mock_client(monkeypatch, balances, prices):
    class FakeClient:
        def __init__(self, _api_key, _api_secret):
            pass

        def get_spot_balances(self):
            return balances

        def get_prices(self, symbols):
            return {symbol: prices[symbol] for symbol in symbols if symbol in prices}

    monkeypatch.setattr(snapshot, "BinanceReadOnlyClient", FakeClient)
    monkeypatch.setenv("BINANCE_API_KEY", "key")
    monkeypatch.setenv("BINANCE_API_SECRET", "secret")


def test_fetch_filters_dust(monkeypatch, tmp_path):
    _mock_client(
        monkeypatch,
        [
            {"asset": "BTC", "free": 0.1, "locked": 0},
            {"asset": "SHIB", "free": 1, "locked": 0},
        ],
        {"BTCUSDT": 60_000, "SHIBUSDT": 0.1},
    )
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    result = snapshot.fetch_and_save(5.0)

    assert [position.asset for position in result.positions] == ["BTC"]


def test_fetch_skips_asset_without_usdt_pair(monkeypatch, tmp_path):
    _mock_client(
        monkeypatch,
        [
            {"asset": "BTC", "free": 0.1, "locked": 0},
            {"asset": "EARN", "free": 100, "locked": 0},
        ],
        {"BTCUSDT": 60_000},
    )
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    result = snapshot.fetch_and_save(5.0)

    assert [position.asset for position in result.positions] == ["BTC"]


def test_usdt_treated_as_one_to_one(monkeypatch, tmp_path):
    _mock_client(monkeypatch, [{"asset": "USDT", "free": 100, "locked": 0}], {})
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    result = snapshot.fetch_and_save(5.0)

    assert result.positions[0].price_usdt == 1.0
    assert result.total_brl == 500.0


def test_total_calculated_correctly(monkeypatch, tmp_path):
    _mock_client(
        monkeypatch,
        [
            {"asset": "BTC", "free": 0.1, "locked": 0},
            {"asset": "USDT", "free": 100, "locked": 0},
        ],
        {"BTCUSDT": 60_000},
    )
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    result = snapshot.fetch_and_save(5.0)

    assert result.total_usdt == pytest.approx(6100)
    assert result.total_brl == pytest.approx(30_500)


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    _mock_client(
        monkeypatch, [{"asset": "ETH", "free": 1, "locked": 0}], {"ETHUSDT": 3000}
    )
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "snapshot.json")

    saved = snapshot.fetch_and_save(5.0)
    loaded = snapshot.load_last_snapshot()

    assert loaded == saved
    assert json.loads((tmp_path / "snapshot.json").read_text())["total_brl"] == 15_000


def test_load_returns_none_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", tmp_path / "missing.json")

    assert snapshot.load_last_snapshot() is None


def test_snapshot_stale_after_four_hours():
    old_timestamp = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    value = snapshot.CryptoSnapshot([], 0, 0, 5, old_timestamp)

    assert value.stale is True

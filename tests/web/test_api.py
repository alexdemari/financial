from fastapi.testclient import TestClient

from web import server
from web.readers import history_jsonl
from web.readers.history_jsonl import AccountSnapshot
from web.readers.ibkr_csv import Position
from web.routers import account, history


def test_account_endpoint_returns_hint_without_data(tmp_path, monkeypatch):
    monkeypatch.setattr(history_jsonl, "HISTORY_PATH", tmp_path / "missing.jsonl")
    response = TestClient(server.app).get("/api/account")
    assert response.status_code == 200
    assert response.json() == {
        "error": "no_data",
        "hint": "Run: just ibkr-positions",
    }


def test_status_endpoint_lists_expected_sources():
    response = TestClient(server.app).get("/api/status")
    names = {entry["name"] for entry in response.json()["files"]}
    assert names == {
        "ibkr_positions",
        "options_tracker",
        "history",
        "scan_daily",
        "scanner_report",
        "dividend_report",
    }


def test_history_rejects_invalid_days():
    response = TestClient(server.app).get("/api/history?days=0")
    assert response.status_code == 422


def test_history_forwards_days_parameter(monkeypatch):
    received = []
    monkeypatch.setattr(
        history, "read_history", lambda days: received.append(days) or []
    )
    response = TestClient(server.app).get("/api/history?days=17")
    assert response.status_code == 200
    assert received == [17]


def test_risk_reports_concentration_and_cash_shortfall(monkeypatch):
    positions = [
        _position("AAPL", "STK", 10, 0.30),
        _position("AAPL PUT", "OPT", -2, 0.05, option_type="PUT", strike=100),
    ]
    snapshot = AccountSnapshot(
        nlv=50_000,
        cash=5_000,
        invested=45_000,
        unrealized_pnl=100,
        unrealized_pnl_pct=0.01,
        margin_utilization=0.2,
        net_delta_approx=50,
        as_of="2026-06-30",
        last_updated="2026-06-30T12:00:00+00:00",
    )
    monkeypatch.setattr(account, "read_positions", lambda: positions)
    monkeypatch.setattr(account, "read_account_snapshot", lambda: snapshot)
    result = account.get_risk()
    assert result["shortfall"] == 15_000
    assert {alert["type"] for alert in result["alerts"]} == {
        "concentration",
        "cash_shortfall",
    }


def _position(
    symbol,
    asset_type,
    quantity,
    weight,
    *,
    option_type=None,
    strike=None,
):
    return Position(
        symbol=symbol,
        asset_type=asset_type,
        quantity=quantity,
        cost_basis=0,
        market_value=0,
        unrealized_pnl=0,
        return_pct=0,
        weight=weight,
        option_type=option_type,
        strike=strike,
        expiration=None,
        dte=None,
        risk_status=None,
    )

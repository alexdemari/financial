from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position
from ibkr_positions.snapshot_store import append_snapshot, load_history, main


def _make_portfolio() -> Portfolio:
    summary = AccountSummary(
        net_liquidation=50000.0,
        total_cash=12000.0,
        buying_power=100000.0,
        initial_margin=12500.0,
        maintenance_margin=10000.0,
        excess_liquidity=37500.0,
    )
    positions = [
        Position(
            symbol="AAPL",
            asset_type="STK",
            quantity=100,
            market_value=18000.0,
            cost_basis=15000.0,
            unrealized_pnl=3000.0,
            currency="USD",
        ),
        Position(
            symbol="PEP",
            asset_type="OPT",
            quantity=-1,
            market_value=-200.0,
            cost_basis=300.0,
            unrealized_pnl=-100.0,
            currency="USD",
            expiration="2027-01-15",
            strike=140.0,
            option_type="PUT",
            underlying="PEP",
            underlying_price=145.0,
        ),
    ]
    return Portfolio(
        account_id="U123456",
        as_of="2026-06-23T10:00:00",
        summary=summary,
        cash=[CashBalance(currency="USD", balance=12000.0, settled_cash=12000.0)],
        positions=positions,
    )


def _patch_today(day: str):
    return patch(
        "ibkr_positions.snapshot_store.date",
        **{"today.return_value.isoformat.return_value": day},
    )


def test_first_snapshot_creates_file(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    with _patch_today("2026-06-23"):
        append_snapshot(_make_portfolio(), history_path=history_path)

    assert history_path.exists()
    lines = [ln for ln in history_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["date"] == "2026-06-23"
    assert entry["nlv"] == 50000.0
    assert entry["cash"] == 12000.0


def test_same_day_upserts(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    with _patch_today("2026-06-23"):
        append_snapshot(_make_portfolio(), history_path=history_path)
        append_snapshot(_make_portfolio(), history_path=history_path)

    lines = [ln for ln in history_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1


def test_different_day_appends(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    for day in ("2026-06-22", "2026-06-23"):
        with _patch_today(day):
            append_snapshot(_make_portfolio(), history_path=history_path)

    lines = [ln for ln in history_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2
    dates = {json.loads(ln)["date"] for ln in lines}
    assert dates == {"2026-06-22", "2026-06-23"}


def test_load_history_sorted(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    raw = [
        {"date": "2026-06-23", "nlv": 50000.0},
        {"date": "2026-06-21", "nlv": 48000.0},
        {"date": "2026-06-22", "nlv": 49000.0},
    ]
    history_path.write_text("\n".join(json.dumps(e) for e in raw) + "\n")

    result = load_history(history_path=history_path)
    assert [r["date"] for r in result] == ["2026-06-21", "2026-06-22", "2026-06-23"]


def test_load_history_days_limit(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    entries = [
        {"date": f"2026-06-{i:02d}", "nlv": float(i * 1000)} for i in range(1, 11)
    ]
    history_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    result = load_history(history_path=history_path, days=3)
    assert len(result) == 3
    assert result[0]["date"] == "2026-06-08"
    assert result[-1]["date"] == "2026-06-10"


def test_load_history_rejects_non_positive_days(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="days must be greater than zero"):
        load_history(history_path=tmp_path / "history.jsonl", days=0)


def test_load_history_missing_file(tmp_path: Path) -> None:
    result = load_history(history_path=tmp_path / "nonexistent.jsonl")
    assert result == []


def test_snapshot_fields_populated(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    with _patch_today("2026-06-23"):
        append_snapshot(_make_portfolio(), history_path=history_path)

    entry = json.loads(history_path.read_text().splitlines()[0])
    assert entry["invested"] == 18000.0 + (-200.0)  # STK + OPT market values
    assert entry["options_premium_received"] == 300.0  # abs(cost_basis) of short OPT
    assert entry["options_current_value"] == -200.0
    assert entry["options_pnl"] == -100.0
    assert entry["stk_pnl"] == 3000.0
    assert entry["unrealized_pnl"] == 3000.0 + (-100.0)
    assert entry["margin_utilization"] == pytest.approx(12500.0 / 50000.0)


def test_history_cli_rejects_non_positive_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--history", str(tmp_path / "history.jsonl"), "--days", "0"])

    assert exc_info.value.code == 2
    assert "must be greater than zero" in capsys.readouterr().err

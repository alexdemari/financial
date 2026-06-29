from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from irpf_report.trades import parse_history_csv


def _write_history(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    history_path = tmp_path / "trades_history.csv"
    pd.DataFrame(rows).to_csv(history_path, index=False)
    return history_path


def _history_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "trade_id": "T1",
        "date": "2025-03-15",
        "symbol": "AAPL",
        "asset_type": "STK",
        "quantity": 10,
        "proceeds": 500.0,
        "pnl_realized": 150.0,
        "currency": "USD",
        "open_close": "C",
    }
    row.update(overrides)
    return row


def test_parse_history_csv_filters_by_year(tmp_path: Path) -> None:
    history_path = _write_history(
        tmp_path,
        [
            _history_row(),
            _history_row(trade_id="T2", date="2024-03-15", symbol="MSFT"),
        ],
    )

    trades = parse_history_csv(history_path, 2025)

    assert [trade.symbol for trade in trades] == ["AAPL"]


def test_parse_history_csv_excludes_open_trades(tmp_path: Path) -> None:
    history_path = _write_history(
        tmp_path,
        [
            _history_row(),
            _history_row(trade_id="T2", symbol="MSFT", open_close="O"),
        ],
    )

    trades = parse_history_csv(history_path, 2025)

    assert [trade.symbol for trade in trades] == ["AAPL"]


def test_parse_history_csv_excludes_cash_rows(tmp_path: Path) -> None:
    history_path = _write_history(
        tmp_path,
        [
            _history_row(),
            _history_row(trade_id="T2", symbol="USD", asset_type="CASH"),
        ],
    )

    trades = parse_history_csv(history_path, 2025)

    assert [trade.symbol for trade in trades] == ["AAPL"]


def test_parse_history_csv_excludes_non_usd_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history_path = _write_history(
        tmp_path,
        [
            _history_row(),
            _history_row(trade_id="T2", symbol="SAP", currency="EUR"),
        ],
    )

    trades = parse_history_csv(history_path, 2025)

    assert [trade.symbol for trade in trades] == ["AAPL"]
    assert "skipped 1 non-USD currency(ies): EUR" in capsys.readouterr().err


def test_parse_history_csv_skips_null_pnl_with_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history_path = _write_history(
        tmp_path, [_history_row(symbol="AAPL", pnl_realized=None)]
    )

    trades = parse_history_csv(history_path, 2025)

    assert trades == []
    assert (
        "⚠ Skipping AAPL 2025-03-15: pnl_realized missing (run just ibkr-flex-fetch)"
    ) in capsys.readouterr().out


def test_parse_history_csv_basis_derived_correctly(tmp_path: Path) -> None:
    history_path = _write_history(tmp_path, [_history_row()])

    trades = parse_history_csv(history_path, 2025)

    assert len(trades) == 1
    assert trades[0].cost_usd == pytest.approx(350.0)
    assert trades[0].pnl_usd == pytest.approx(150.0)

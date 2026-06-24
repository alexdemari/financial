from __future__ import annotations

import csv
from pathlib import Path

import pytest

from irpf_report.trades import parse_ibkr_csv

_HEADERS = [
    "DataDiscriminator",
    "Asset Category",
    "Currency",
    "Symbol",
    "Date/Time",
    "Quantity",
    "T. Price",
    "Proceeds",
    "Comm/Fee",
    "Basis",
    "Realized P/L",
    "Code",
]


def _make_csv(rows: list[dict], tmp_path: Path) -> Path:
    path = tmp_path / "trades.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _trade_row(
    discriminator: str = "Trade",
    code: str = "C",
    symbol: str = "AAPL",
    asset: str = "Stocks",
    dt: str = "2025-03-15 10:00:00",
    qty: str = "50",
    proceeds: str = "1500.00",
    basis: str = "-1250.00",
    pnl: str = "250.00",
) -> dict:
    return {
        "DataDiscriminator": discriminator,
        "Asset Category": asset,
        "Currency": "USD",
        "Symbol": symbol,
        "Date/Time": dt,
        "Quantity": qty,
        "T. Price": "30.00",
        "Proceeds": proceeds,
        "Comm/Fee": "-1.00",
        "Basis": basis,
        "Realized P/L": pnl,
        "Code": code,
    }


def test_parse_ibkr_csv_returns_only_closed_trades(tmp_path: Path) -> None:
    rows = [
        _trade_row(code="C", symbol="AAPL"),
        _trade_row(code="O", symbol="MSFT"),  # open — must be excluded
        _trade_row(code="O;C", symbol="GOOG"),  # open+close in one row — included
    ]
    path = _make_csv(rows, tmp_path)
    trades = parse_ibkr_csv(path)

    symbols = {t.symbol for t in trades}
    assert "AAPL" in symbols
    assert "GOOG" in symbols
    assert "MSFT" not in symbols
    assert len(trades) == 2


def test_trade_pnl_usd_is_correct(tmp_path: Path) -> None:
    rows = [_trade_row(proceeds="1500.00", basis="-1250.00", pnl="250.00")]
    path = _make_csv(rows, tmp_path)
    trades = parse_ibkr_csv(path)

    assert len(trades) == 1
    t = trades[0]
    assert t.proceeds_usd == pytest.approx(1500.00)
    assert t.cost_usd == pytest.approx(1250.00)
    assert t.pnl_usd == pytest.approx(250.00)


def test_non_usd_trades_are_excluded(tmp_path: Path) -> None:
    eur_row = _trade_row(symbol="DAX")
    eur_row["Currency"] = "EUR"
    rows = [
        eur_row,
        _trade_row(symbol="AAPL"),
    ]
    path = _make_csv(rows, tmp_path)
    trades = parse_ibkr_csv(path)

    assert len(trades) == 1
    assert trades[0].symbol == "AAPL"


def test_non_trade_rows_are_excluded(tmp_path: Path) -> None:
    rows = [
        _trade_row(discriminator="SubTotal", code="C", symbol="IBM"),
        _trade_row(discriminator="Trade", code="C", symbol="AAPL"),
    ]
    path = _make_csv(rows, tmp_path)
    trades = parse_ibkr_csv(path)

    assert len(trades) == 1
    assert trades[0].symbol == "AAPL"

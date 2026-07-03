from __future__ import annotations

import pandas as pd

from web.readers import trades_reader


def _write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def _ibkr_trade(**overrides):
    trade = {
        "trade_id": "1",
        "date": "2026-06-10",
        "symbol": "AAPL  260717C00310000",
        "underlying": "AAPL",
        "asset_type": "OPT",
        "option_type": "CALL",
        "strike": 310,
        "expiration": "2026-07-17",
        "quantity": 1,
        "price": 2.5,
        "proceeds": -250,
        "commission": -1,
        "pnl_realized": 50,
        "currency": "USD",
        "open_close": "C",
        "strategy": "covered_call",
    }
    trade.update(overrides)
    return trade


def _set_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(trades_reader, "IBKR_HISTORY", tmp_path / "ibkr.csv")
    monkeypatch.setattr(trades_reader, "BTG_OPCOES", tmp_path / "btg_options.csv")
    monkeypatch.setattr(trades_reader, "BTG_GERAL", tmp_path / "btg_general.csv")


def test_read_ibkr_trades_returns_only_closed_with_realized_pnl(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    _write_csv(
        trades_reader.IBKR_HISTORY,
        [
            _ibkr_trade(trade_id="open", open_close="O"),
            _ibkr_trade(trade_id="closed", open_close="C"),
            _ibkr_trade(trade_id="missing-pnl", pnl_realized=None),
        ],
    )

    trades = trades_reader.read_all_trades()

    assert len(trades) == 1
    assert trades[0]["pnl_realized"] == 50


def test_read_btg_trades_returns_empty_when_file_missing(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)

    assert trades_reader._read_btg_trades(trades_reader.BTG_OPCOES, "BTG-Opções") == []


def test_trade_row_has_all_required_fields(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    _write_csv(trades_reader.IBKR_HISTORY, [_ibkr_trade()])

    trade = trades_reader.read_all_trades()[0]

    assert set(trade) == {
        "date",
        "broker",
        "symbol",
        "underlying",
        "asset_type",
        "direction",
        "quantity",
        "price",
        "proceeds",
        "commission",
        "pnl_realized",
        "currency",
        "strategy",
        "option_type",
        "strike",
        "expiration",
    }
    assert trade["broker"] == "IBKR"
    assert trade["currency"] == "USD"
    assert trade["direction"] == "BUY"


def test_monthly_summary_groups_by_month_and_currency():
    trades = [
        {"date": "2026-06-01", "currency": "USD", "pnl_realized": 100},
        {"date": "2026-06-02", "currency": "USD", "pnl_realized": -40},
        {"date": "2026-06-03", "currency": "BRL", "pnl_realized": 80},
    ]

    summaries = trades_reader.read_monthly_summary(trades)

    assert summaries == [
        {
            "month": "2026-06",
            "currency": "USD",
            "gross_gains": 100.0,
            "gross_losses": -40.0,
            "net_pnl": 60.0,
            "trade_count": 2,
        },
        {
            "month": "2026-06",
            "currency": "BRL",
            "gross_gains": 80.0,
            "gross_losses": 0.0,
            "net_pnl": 80.0,
            "trade_count": 1,
        },
    ]


def test_merged_trades_sorted_by_date_descending(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    _write_csv(trades_reader.IBKR_HISTORY, [_ibkr_trade(date="2026-06-01")])
    _write_csv(
        trades_reader.BTG_GERAL,
        [
            {
                "date": "2026-05-15",
                "symbol": "TAEE11",
                "asset_type": "ACAO",
                "direction": "SELL",
                "quantity": 10,
                "price": 40,
                "proceeds": 400,
                "commission": -1,
                "pnl_realized": 20,
                "currency": "BRL",
            }
        ],
    )

    trades = trades_reader.read_all_trades()

    assert [trade["broker"] for trade in trades] == ["IBKR", "BTG-Geral"]
    assert trades[1]["asset_type"] == "STK"


def test_sources_include_mtime_for_existing_files(tmp_path, monkeypatch):
    _set_paths(monkeypatch, tmp_path)
    _write_csv(trades_reader.IBKR_HISTORY, [_ibkr_trade()])

    sources = trades_reader.read_trade_sources()

    assert sources["ibkr"]["last_updated"]
    assert sources["btg_opcoes"] is None

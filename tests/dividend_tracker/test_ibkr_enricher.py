from pathlib import Path

import pandas as pd
import pytest

from dividend_tracker.ibkr_enricher import (
    IBKRHolding,
    load_ibkr_stk_positions,
    project_annual_income,
)


def _write_positions_csv(tmp_path, rows: list[dict]) -> "Path":
    path = tmp_path / "ibkr_positions_2026-06-24.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


_BASE_COLUMNS = [
    "symbol",
    "type",
    "qty",
    "market_value",
    "cost_basis",
    "unrealized_pnl",
    "weight",
    "available_cash",
]


def test_load_ibkr_stk_positions_filters_out_options(tmp_path):
    rows = [
        {
            "symbol": "SGOV",
            "type": "STK",
            "qty": 200.0,
            "market_value": 20120.0,
            "cost_basis": 19900.0,
            "unrealized_pnl": 220.0,
            "weight": 0.40,
            "available_cash": 13522.8,
        },
        {
            "symbol": "AAPL  260717C00310000",
            "type": "OPT",
            "qty": -1.0,
            "market_value": -250.0,
            "cost_basis": 310.94,
            "unrealized_pnl": 60.94,
            "weight": 0.004,
            "available_cash": 13522.8,
        },
    ]
    csv_path = _write_positions_csv(tmp_path, rows)
    holdings, cash = load_ibkr_stk_positions(csv_path)

    assert list(holdings.keys()) == ["SGOV"]
    assert holdings["SGOV"].quantity == 200.0
    assert cash == pytest.approx(13522.8)


def test_project_annual_income_multiplies_shares_by_div(tmp_path):
    holdings = {
        "SGOV": IBKRHolding(
            symbol="SGOV",
            quantity=200.0,
            market_value=20120.0,
            cost_basis=19900.0,
        )
    }
    dividend_data = {"SGOV": 5.18}
    results = project_annual_income(holdings, dividend_data)

    assert len(results) == 1
    row = results[0]
    assert row["symbol"] == "SGOV"
    assert row["shares"] == 200.0
    assert row["projected_annual_income_usd"] == pytest.approx(1036.0)
    assert row["annual_div_per_share"] == pytest.approx(5.18)


def test_ibkr_enricher_skips_symbol_not_in_dividend_data():
    holdings = {
        "AAPL": IBKRHolding(
            symbol="AAPL",
            quantity=100.0,
            market_value=29725.0,
            cost_basis=26500.0,
        )
    }
    dividend_data: dict[str, float] = {}
    results = project_annual_income(holdings, dividend_data)

    assert results == []

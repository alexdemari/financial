from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ibkr_positions.models import AccountSummary, Portfolio, Position
from ibkr_positions.options_export import (
    OPTIONS_TRACKER_LIVE_COLUMNS,
    write_options_tracker_live_csv,
)
from market_scanner.options_tracker_schema import OPTIONS_TRACKER_COLUMNS
from market_scanner.portfolio import load_open_positions


def _portfolio(positions: list[Position]) -> Portfolio:
    return Portfolio(
        account_id="U1234567",
        as_of="2026-06-23T10:00:00+00:00",
        summary=AccountSummary(
            net_liquidation=50000.0,
            total_cash=10000.0,
            buying_power=20000.0,
            initial_margin=5000.0,
            maintenance_margin=3000.0,
            excess_liquidity=45000.0,
        ),
        cash=[],
        positions=positions,
    )


def _stock_position() -> Position:
    return Position(
        symbol="AAPL",
        asset_type="STK",
        quantity=100.0,
        market_value=18000.0,
        cost_basis=15000.0,
        unrealized_pnl=3000.0,
        currency="USD",
    )


def _option_position(
    symbol: str = "PEP 260717P00140000",
    underlying: str | None = "PEP",
    quantity: float = -1.0,
    cost_basis: float = 286.0,
    expiration: str = "2026-07-17",
) -> Position:
    return Position(
        symbol=symbol,
        asset_type="OPT",
        quantity=quantity,
        market_value=-143.0,
        cost_basis=cost_basis,
        unrealized_pnl=143.0,
        currency="USD",
        expiration=expiration,
        strike=140.0,
        option_type="PUT",
        underlying=underlying,
        delta=-0.25,
    )


def _read_live_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";")


def test_option_positions_are_extracted_from_portfolio(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_stock_position(), _option_position()]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "PEP"


def test_dte_computed_correctly(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position()]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert result.iloc[0]["dte"] == 24


def test_csv_schema_matches_options_tracker_columns(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position()]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert list(result.columns) == OPTIONS_TRACKER_LIVE_COLUMNS
    assert tuple(OPTIONS_TRACKER_LIVE_COLUMNS) == OPTIONS_TRACKER_COLUMNS
    assert {
        "symbol",
        "underlying",
        "option_type",
        "strike",
        "expiration",
        "quantity",
        "premium_received",
        "current_value",
        "unrealized_pnl",
        "dte",
    }.issubset(result.columns)


def test_short_position_premium_maps_to_cost_basis(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position(cost_basis=312.5)]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path).astype({"premium_received": "string"})

    assert result.iloc[0]["open_direction"] == "V"
    assert result.iloc[0]["premium_received"] == "312,50"


def test_no_options_produces_empty_csv_not_error(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_stock_position()]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert result.empty
    assert list(result.columns) == OPTIONS_TRACKER_LIVE_COLUMNS


def test_exported_csv_can_feed_exit_monitor_portfolio_loader(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position()]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    positions = load_open_positions(csv_path)

    assert len(positions) == 1
    assert positions[0].symbol == "PEP"
    assert positions[0].entry_date is None
    assert positions[0].option_expiry == date(2026, 7, 17)
    assert positions[0].premium_paid == pytest.approx(286.0)


@pytest.mark.parametrize(
    ("quantity", "expected_contracts"),
    [(-5.0, -5.0), (-12.0, -12.0), (1.5, 1.5)],
)
def test_contract_quantity_round_trip(
    tmp_path: Path,
    quantity: float,
    expected_contracts: float,
):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position(quantity=quantity)]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    positions = load_open_positions(csv_path)

    assert positions[0].contracts == expected_contracts


def test_compact_expiration_is_exported(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position(expiration="20260717")]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert len(result) == 1
    assert result.iloc[0]["expiration"] == "2026-07-17"


def test_invalid_expiration_skips_only_bad_position(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    csv_path = write_options_tracker_live_csv(
        _portfolio(
            [
                _option_position(symbol="BAD", expiration="not-a-date"),
                _option_position(symbol="GOOD"),
            ]
        ),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "PEP"
    assert "invalid expiration" in caplog.text


def test_missing_underlying_is_skipped(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position(underlying=None)]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    result = _read_live_csv(csv_path)

    assert result.empty
    assert "missing underlying symbol" in caplog.text


def test_zero_quantity_option_is_not_exported(tmp_path: Path):
    csv_path = write_options_tracker_live_csv(
        _portfolio([_option_position(quantity=0.0)]),
        output_dir=tmp_path,
        as_of=date(2026, 6, 23),
    )

    assert _read_live_csv(csv_path).empty

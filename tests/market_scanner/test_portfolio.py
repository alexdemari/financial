"""Tests for portfolio.py — CSV parsing and side derivation."""

from datetime import date
from pathlib import Path

import pytest

from market_scanner.portfolio import (
    _derive_side,
    load_open_positions,
)

# ---------------------------------------------------------------------------
# _parse_european_float
# ---------------------------------------------------------------------------


def test_parse_european_float_normal():
    from market_scanner.portfolio import _parse_european_float

    assert _parse_european_float("1,45") == pytest.approx(1.45)


def test_parse_european_float_negative():
    from market_scanner.portfolio import _parse_european_float

    assert _parse_european_float("-0,78") == pytest.approx(-0.78)


def test_parse_european_float_empty():
    from market_scanner.portfolio import _parse_european_float

    assert _parse_european_float("") is None


def test_parse_european_float_thousands():
    from market_scanner.portfolio import _parse_european_float

    assert _parse_european_float("1.234,56") == pytest.approx(1234.56)


def test_parse_date_iso_format():
    from market_scanner.portfolio import _parse_date

    assert _parse_date("2026-07-17") == date(2026, 7, 17)


@pytest.mark.parametrize(
    "value",
    ["2026-07-17T10:00:00", "2026-07-17 10:00:00", "2026-07-17T10:00:00Z"],
)
def test_parse_date_iso_datetime(value):
    from market_scanner.portfolio import _parse_date

    assert _parse_date(value) == date(2026, 7, 17)


# ---------------------------------------------------------------------------
# _derive_side
# ---------------------------------------------------------------------------


def test_derive_side_short_put_is_bullish():
    assert _derive_side("PUT", "V") == "bullish"


def test_derive_side_long_put_is_bearish():
    assert _derive_side("PUT", "C") == "bearish"


def test_derive_side_short_call_is_bearish():
    assert _derive_side("CALL", "V") == "bearish"


def test_derive_side_long_call_is_bullish():
    assert _derive_side("CALL", "C") == "bullish"


# ---------------------------------------------------------------------------
# load_open_positions
# ---------------------------------------------------------------------------

_HEADER = "Date;Plataform;USD/BRL;Asset;Code;Type;C/V;Due date;Strike;Value (Un.);Qty (Contracts);Costs;Total C/D;Delta;IV;POP;Colateral;Close Action;Close Date;Qty (Contracts);Value (Un.);Costs;Result;Size;Close Description;signal_source"


def _write_csv(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "options_tracker.csv"
    content = "\r\n".join([_HEADER] + rows) + "\r\n"
    path.write_bytes(content.encode("utf-8"))
    return path


def _open_row(
    asset="AAPL",
    typ="PUT",
    cv="V",
    expiry="18/06/2026",
    strike="50,00",
    premium="1,45",
    contracts="1",
    delta="-0,25",
    iv="25,00",
    signal_source="lux",
    entry_date="26/05/2026",
):
    # Close Date (col 18) is empty → open position
    return f"{entry_date};IBKR;USD;{asset};;{typ};{cv};{expiry};{strike};{premium};{contracts};-0,77;143,23;{delta};{iv};75%;;;;;;;;;;{signal_source}"


def _closed_row():
    return "10/01/2026;IBKR;USD;MSFT;;PUT;V;20/02/2026;400,00;2,50;1;-0,77;249,23;-0,2;20,00;80%;;Compra;15/01/2026;1;-1,20;-0,77;128,46;0;Lucro;"


def test_load_open_positions_returns_empty_when_file_missing(tmp_path):
    result = load_open_positions(tmp_path / "nonexistent.csv")
    assert result == []


def test_load_open_positions_skips_closed_rows(tmp_path):
    path = _write_csv(tmp_path, [_closed_row()])
    result = load_open_positions(path)
    assert result == []


def test_load_open_positions_skips_empty_asset_rows(tmp_path):
    path = _write_csv(tmp_path, [";;;;;;;;;;;;;;;;;;;;;;;;;;"])
    result = load_open_positions(path)
    assert result == []


def test_load_open_positions_parses_open_row(tmp_path):
    path = _write_csv(tmp_path, [_open_row()])
    result = load_open_positions(path)
    assert len(result) == 1
    pos = result[0]
    assert pos.symbol == "AAPL"
    assert pos.side == "bullish"  # PUT + V = short put = bullish
    assert pos.option_type == "put"
    assert pos.option_direction == "short"
    assert pos.option_strike == pytest.approx(50.0)
    assert pos.premium_paid == pytest.approx(1.45)
    assert pos.contracts == 1
    assert pos.delta == pytest.approx(-0.25)
    assert pos.entry_date == date(2026, 5, 26)
    assert pos.option_expiry == date(2026, 6, 18)
    assert pos.signal_source == "lux"


def test_load_open_positions_skips_closed_keeps_open(tmp_path):
    path = _write_csv(tmp_path, [_closed_row(), _open_row(asset="TFC")])
    result = load_open_positions(path)
    assert len(result) == 1
    assert result[0].symbol == "TFC"


def test_load_open_positions_long_call_is_bullish(tmp_path):
    path = _write_csv(tmp_path, [_open_row(typ="CALL", cv="C")])
    result = load_open_positions(path)
    assert result[0].side == "bullish"
    assert result[0].option_direction == "long"


def test_load_open_positions_preserves_missing_entry_date(tmp_path, caplog):
    path = _write_csv(
        tmp_path,
        [_open_row(entry_date="", signal_source="ibkr_live")],
    )

    result = load_open_positions(path)

    assert len(result) == 1
    assert result[0].entry_date is None
    assert "no valid entry date" in caplog.text


def test_load_open_positions_parses_fractional_contracts(tmp_path):
    path = _write_csv(tmp_path, [_open_row(contracts="1,5")])

    result = load_open_positions(path)

    assert result[0].contracts == pytest.approx(1.5)

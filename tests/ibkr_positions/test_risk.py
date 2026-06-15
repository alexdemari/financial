from datetime import date, timedelta

import pytest

from ibkr_positions.models import AccountSummary, Position
from ibkr_positions.risk import (
    cash_coverage,
    concentration_risk,
    covered_calls_itm,
    margin_utilization,
    options_expiring_soon,
    short_puts_near_assignment,
)


def _stock(symbol: str, market_value: float) -> Position:
    return Position(
        symbol=symbol,
        asset_type="STK",
        quantity=100.0,
        market_value=market_value,
        cost_basis=market_value,
        unrealized_pnl=0.0,
        currency="USD",
    )


def _put(
    symbol: str,
    quantity: float,
    strike: float,
    underlying_price: float,
    expiration: str | None = None,
    market_value: float = -100.0,
) -> Position:
    return Position(
        symbol=symbol,
        asset_type="OPT",
        quantity=quantity,
        market_value=market_value,
        cost_basis=100.0,
        unrealized_pnl=0.0,
        currency="USD",
        expiration=expiration,
        strike=strike,
        option_type="PUT",
        underlying="AAPL",
        delta=-0.3,
        underlying_price=underlying_price,
    )


def _call(
    symbol: str,
    quantity: float,
    strike: float,
    underlying_price: float,
    expiration: str | None = None,
) -> Position:
    return Position(
        symbol=symbol,
        asset_type="OPT",
        quantity=quantity,
        market_value=-100.0,
        cost_basis=100.0,
        unrealized_pnl=0.0,
        currency="USD",
        expiration=expiration,
        strike=strike,
        option_type="CALL",
        underlying="AAPL",
        delta=0.3,
        underlying_price=underlying_price,
    )


def _summary(nlv: float, cash: float = 5000.0, margin: float = 0.0) -> AccountSummary:
    return AccountSummary(
        net_liquidation=nlv,
        total_cash=cash,
        buying_power=nlv * 2,
        initial_margin=margin,
        maintenance_margin=margin * 0.7,
        excess_liquidity=nlv - margin,
    )


# concentration_risk


def test_concentration_risk_flags_large_position():
    positions = [_stock("AAPL", 30000.0), _stock("MSFT", 10000.0)]
    flagged = concentration_risk(positions, threshold=0.25)
    assert "AAPL" in flagged
    assert "MSFT" not in flagged


def test_concentration_risk_no_flag_when_all_below_threshold():
    positions = [
        _stock("A", 10.0),
        _stock("B", 10.0),
        _stock("C", 10.0),
        _stock("D", 10.0),
    ]
    assert concentration_risk(positions, threshold=0.25) == []


def test_concentration_risk_empty_positions():
    assert concentration_risk([]) == []


# options_expiring_soon


def test_options_expiring_soon_flags_near_expiry():
    soon = (date.today() + timedelta(days=3)).isoformat()
    far = (date.today() + timedelta(days=30)).isoformat()
    positions = [
        _put("OPT_NEAR", -1.0, 100.0, 105.0, expiration=soon),
        _put("OPT_FAR", -1.0, 100.0, 105.0, expiration=far),
    ]
    expiring = options_expiring_soon(positions, days=7)
    symbols = [p.symbol for p in expiring]
    assert "OPT_NEAR" in symbols
    assert "OPT_FAR" not in symbols


def test_options_expiring_soon_empty():
    assert options_expiring_soon([], days=7) == []


def test_options_expiring_soon_skips_non_options():
    assert options_expiring_soon([_stock("AAPL", 10000.0)], days=7) == []


# short_puts_near_assignment


def test_short_puts_near_assignment_flags_within_buffer():
    # strike=140, underlying=142 → distance=(142-140)/140=1.4% < 5%
    positions = [_put("NEAR_PUT", -1.0, 140.0, 142.0)]
    assert len(short_puts_near_assignment(positions, buffer_pct=0.05)) == 1


def test_short_puts_near_assignment_no_flag_when_far():
    # strike=140, underlying=200 → distance=42% > 5%
    positions = [_put("FAR_PUT", -1.0, 140.0, 200.0)]
    assert short_puts_near_assignment(positions, buffer_pct=0.05) == []


def test_short_puts_near_assignment_skips_long_puts():
    positions = [_put("LONG_PUT", +1.0, 140.0, 142.0)]
    assert short_puts_near_assignment(positions) == []


def test_short_puts_near_assignment_empty():
    assert short_puts_near_assignment([]) == []


# covered_calls_itm


def test_covered_calls_itm_flags_itm_short_call():
    # strike=140, underlying=150 → ITM
    positions = [_call("ITM_CALL", -1.0, 140.0, 150.0)]
    assert len(covered_calls_itm(positions)) == 1


def test_covered_calls_itm_no_flag_when_otm():
    # strike=160, underlying=150 → OTM
    positions = [_call("OTM_CALL", -1.0, 160.0, 150.0)]
    assert covered_calls_itm(positions) == []


def test_covered_calls_itm_skips_long_calls():
    positions = [_call("LONG_CALL", +1.0, 140.0, 150.0)]
    assert covered_calls_itm(positions) == []


def test_covered_calls_itm_empty():
    assert covered_calls_itm([]) == []


# margin_utilization


def test_margin_utilization_correct_ratio():
    s = _summary(nlv=50000.0, margin=10000.0)
    assert margin_utilization(s) == pytest.approx(0.2)


def test_margin_utilization_zero_nlv():
    s = _summary(nlv=0.0, margin=0.0)
    assert margin_utilization(s) == 0.0


# cash_coverage


def test_cash_coverage_covered():
    s = _summary(nlv=50000.0, cash=20000.0)
    # short put: qty=-1, strike=140 → worst case = 1 × 140 × 100 = $14,000
    positions = [_put("SHORT_PUT", -1.0, 140.0, 152.0)]
    result = cash_coverage(s, positions)
    assert result["worst_case_assignment_cost"] == pytest.approx(14000.0)
    assert result["available_cash"] == pytest.approx(20000.0)
    assert result["covered"] == 1.0
    assert result["shortfall"] == pytest.approx(0.0)


def test_cash_coverage_shortfall():
    s = _summary(nlv=50000.0, cash=5000.0)
    positions = [_put("SHORT_PUT", -1.0, 140.0, 152.0)]
    result = cash_coverage(s, positions)
    assert result["shortfall"] == pytest.approx(9000.0)
    assert result["covered"] == 0.0


def test_cash_coverage_no_short_puts():
    s = _summary(nlv=50000.0, cash=10000.0)
    result = cash_coverage(s, [_stock("AAPL", 10000.0)])
    assert result["worst_case_assignment_cost"] == 0.0

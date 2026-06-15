from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position


def test_position_stock_defaults():
    p = Position(
        symbol="AAPL",
        asset_type="STK",
        quantity=100.0,
        market_value=18000.0,
        cost_basis=15000.0,
        unrealized_pnl=3000.0,
        currency="USD",
    )
    assert p.expiration is None
    assert p.strike is None
    assert p.option_type is None
    assert p.underlying is None
    assert p.delta is None
    assert p.underlying_price is None


def test_position_option_all_fields():
    p = Position(
        symbol="PEP 15JAN2027 140 P",
        asset_type="OPT",
        quantity=-1.0,
        market_value=-286.0,
        cost_basis=286.0,
        unrealized_pnl=0.0,
        currency="USD",
        expiration="2027-01-15",
        strike=140.0,
        option_type="PUT",
        underlying="PEP",
        delta=-0.32,
        underlying_price=152.0,
    )
    assert p.option_type == "PUT"
    assert p.strike == 140.0
    assert p.underlying == "PEP"
    assert p.delta == -0.32
    assert p.underlying_price == 152.0


def test_account_summary_all_fields():
    s = AccountSummary(
        net_liquidation=50000.0,
        total_cash=10000.0,
        buying_power=20000.0,
        initial_margin=5000.0,
        maintenance_margin=3000.0,
        excess_liquidity=45000.0,
        leverage=0.1,
    )
    assert s.net_liquidation == 50000.0
    assert s.leverage == 0.1


def test_account_summary_leverage_optional():
    s = AccountSummary(
        net_liquidation=50000.0,
        total_cash=10000.0,
        buying_power=20000.0,
        initial_margin=5000.0,
        maintenance_margin=3000.0,
        excess_liquidity=45000.0,
    )
    assert s.leverage is None


def test_portfolio_fields():
    summary = AccountSummary(
        net_liquidation=50000.0,
        total_cash=10000.0,
        buying_power=20000.0,
        initial_margin=5000.0,
        maintenance_margin=3000.0,
        excess_liquidity=45000.0,
    )
    portfolio = Portfolio(
        account_id="U1234567",
        as_of="2026-06-15T10:00:00+00:00",
        summary=summary,
        cash=[CashBalance(currency="USD", balance=10000.0, settled_cash=9800.0)],
        positions=[],
    )
    assert portfolio.account_id == "U1234567"
    assert len(portfolio.positions) == 0
    assert len(portfolio.cash) == 1

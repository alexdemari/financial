from datetime import UTC, datetime
from pathlib import Path

from ibkr_positions.models import AccountSummary, CashBalance, Portfolio, Position
from ibkr_positions.report import render_positions_report, write_positions_report


def _summary(nlv: float = 50000.0, cash: float = 10000.0) -> AccountSummary:
    return AccountSummary(
        net_liquidation=nlv,
        total_cash=cash,
        buying_power=20000.0,
        initial_margin=5000.0,
        maintenance_margin=3000.0,
        excess_liquidity=45000.0,
    )


def _make_portfolio(
    positions: list[Position] | None = None,
    cash_balance: float = 10000.0,
    nlv: float = 50000.0,
) -> Portfolio:
    return Portfolio(
        account_id="U1234567",
        as_of="2026-06-15T10:00:00+00:00",
        summary=_summary(nlv=nlv, cash=cash_balance),
        cash=[
            CashBalance(
                currency="USD",
                balance=cash_balance,
                settled_cash=cash_balance * 0.98,
            )
        ],
        positions=positions or [],
    )


_STOCK = Position(
    symbol="AAPL",
    asset_type="STK",
    quantity=100.0,
    market_value=18000.0,
    cost_basis=15000.0,
    unrealized_pnl=3000.0,
    currency="USD",
)

_OPTION = Position(
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


def test_render_report_includes_title_and_date():
    report = render_positions_report(
        _make_portfolio(),
        generated_at=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
    )
    assert "# IBKR Positions Report — 2026-06-15 10:00" in report


def test_render_report_executive_summary_values():
    report = render_positions_report(_make_portfolio(nlv=50000.0, cash_balance=10000.0))
    assert "$50,000.00" in report  # Net Liquidation
    assert "$10,000.00" in report  # Total Cash


def test_render_report_all_sections_present():
    report = render_positions_report(_make_portfolio())
    assert "## 1. Executive Summary" in report
    assert "## 2. Cash by Currency" in report
    assert "## 3. Portfolio Allocation" in report
    assert "## 4. Consolidated Positions" in report
    assert "## 5. Open Options" in report
    assert "## 6. Risk Analysis" in report
    assert "## 7. Enhanced Risk" in report
    assert "## 8. Actionable Insights" in report


def test_render_report_empty_positions_no_crash():
    report = render_positions_report(_make_portfolio(positions=[]))
    assert "## 4. Consolidated Positions" in report
    assert "## 5. Open Options" in report


def test_render_report_stock_position_appears():
    report = render_positions_report(_make_portfolio(positions=[_STOCK]))
    assert "AAPL" in report
    assert "STK" in report


def test_render_report_option_in_section_5():
    report = render_positions_report(_make_portfolio(positions=[_OPTION]))
    assert "PEP" in report
    assert "PUT" in report
    assert "2027-01-15" in report


def test_render_report_includes_enhanced_risk_details():
    concentrated_stock = Position(
        symbol="AAPL",
        asset_type="STK",
        quantity=100.0,
        market_value=30000.0,
        cost_basis=25000.0,
        unrealized_pnl=5000.0,
        currency="USD",
    )
    short_put = Position(
        symbol="PEP 15JAN2027 140 P",
        asset_type="OPT",
        quantity=-1.0,
        market_value=-286.0,
        cost_basis=286.0,
        unrealized_pnl=-100.0,
        currency="USD",
        expiration="2027-01-15",
        strike=140.0,
        option_type="PUT",
        underlying="PEP",
        underlying_price=152.0,
    )

    report = render_positions_report(
        _make_portfolio(
            positions=[concentrated_stock, short_put],
            cash_balance=1000.0,
            nlv=50000.0,
        )
    )

    assert "Net option delta:" in report
    assert "CLOSE PEP 15JAN2027 140 P" in report
    assert "AAPL: 60.0% of NLV" in report


def test_render_report_no_technical_columns():
    report = render_positions_report(_make_portfolio())
    assert "lux_role" not in report
    assert "action_bucket" not in report


def test_write_positions_report_creates_md_and_csv(tmp_path: Path):
    generated_at = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
    md_path, csv_path, html_path = write_positions_report(
        _make_portfolio(positions=[_STOCK]),
        output_dir=tmp_path,
        generated_at=generated_at,
    )
    assert md_path.exists()
    assert csv_path.exists()
    assert html_path.exists()
    assert md_path.name == "ibkr_positions_2026-06-15.md"
    assert csv_path.name == "ibkr_positions_2026-06-15.csv"
    assert html_path.name == "ibkr_positions_2026-06-15.html"


def test_write_positions_report_csv_has_correct_columns(tmp_path: Path):
    _, csv_path, _html = write_positions_report(
        _make_portfolio(positions=[_STOCK]),
        output_dir=tmp_path,
    )
    content = csv_path.read_text()
    assert (
        "symbol,type,qty,market_value,cost_basis,unrealized_pnl,weight,underlying,"
        "option_type,strike,expiration,available_cash,cash_shortfall,"
        "net_portfolio_delta" in content
    )
    assert "AAPL" in content


def test_write_positions_report_creates_output_dir(tmp_path: Path):
    output_dir = tmp_path / "nested" / "output"
    md_path, csv_path, html_path = write_positions_report(
        _make_portfolio(),
        output_dir=output_dir,
    )
    assert output_dir.exists()
    assert md_path.exists()
    assert csv_path.exists()
    assert html_path.exists()

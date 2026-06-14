from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.decision import AssetDecision, evaluate_asset
from dividend_tracker.price_ceiling import PriceCeilingResult


def _asset(ticker: str = "EGIE3", target_weight: float = 1.0) -> DividendAssetConfig:
    return DividendAssetConfig(
        ticker=ticker,
        sector="Energia",
        name="Engie",
        target_weight=target_weight,
        market="BR",
    )


def _ceiling(
    current_price: float, price_ceiling: float, min_dy: float = 0.06
) -> PriceCeilingResult:
    return PriceCeilingResult(
        ticker="EGIE3",
        price_ceiling=price_ceiling,
        current_dy=0.06,
        trailing_annual_dividends=3.0,
        current_price=current_price,
        margin_pct=(price_ceiling - current_price) / current_price,
        min_dy=min_dy,
    )


def test_buy_when_price_below_ceiling():
    result = evaluate_asset(_asset(), _ceiling(40.0, 50.0))

    assert result.action == "BUY"


def test_overpriced_when_price_above_ceiling():
    result = evaluate_asset(_asset(), _ceiling(60.0, 50.0))

    assert result.action == "OVERPRICED"


def test_price_exactly_at_ceiling_is_buy():
    result = evaluate_asset(_asset(), _ceiling(50.0, 50.0))

    assert result.action == "BUY"


def test_evaluate_asset_returns_asset_decision():
    asset = _asset()
    ceiling = _ceiling(40.0, 50.0)

    result = evaluate_asset(asset, ceiling)

    assert isinstance(result, AssetDecision)
    assert result.asset is asset
    assert result.price_ceiling is ceiling


def test_budget_proportional_to_target_weight():
    from dividend_tracker.report import render_dividend_report

    heavy = DividendAssetConfig(
        ticker="HEAVY",
        sector="Energia",
        name="Heavy",
        target_weight=3.0,
        market="BR",
    )
    light = DividendAssetConfig(
        ticker="LIGHT",
        sector="Energia",
        name="Light",
        target_weight=1.0,
        market="BR",
    )
    decisions = [
        evaluate_asset(heavy, _ceiling(10.0, 20.0)),
        evaluate_asset(light, _ceiling(10.0, 20.0)),
    ]

    report = render_dividend_report(decisions, budget=4000.0)

    # heavy gets 75% = R$3000, light gets 25% = R$1000
    assert "R$3,000.00" in report
    assert "R$1,000.00" in report


def test_budget_skips_overpriced():
    from dividend_tracker.report import render_dividend_report

    buy_asset = DividendAssetConfig(
        ticker="BUY",
        sector="Energia",
        name="Buy",
        target_weight=1.0,
        market="BR",
    )
    over_asset = DividendAssetConfig(
        ticker="OVER",
        sector="Energia",
        name="Over",
        target_weight=1.0,
        market="BR",
    )
    decisions = [
        evaluate_asset(buy_asset, _ceiling(40.0, 50.0)),
        evaluate_asset(over_asset, _ceiling(60.0, 50.0)),
    ]

    report = render_dividend_report(decisions, budget=1000.0)
    budget_section = report.split("## Guia de Aporte", maxsplit=1)[1]

    assert "BUY" in budget_section
    assert "OVER" not in budget_section


def test_zero_weight_excluded_from_budget():
    from dividend_tracker.report import render_dividend_report

    monitored = DividendAssetConfig(
        ticker="WATCH",
        sector="Consumer Staples",
        name="Watched",
        target_weight=0.0,
        market="US",
        notes="Monitored",
    )
    regular = DividendAssetConfig(
        ticker="REG",
        sector="Energia",
        name="Regular",
        target_weight=1.0,
        market="BR",
    )
    decisions = [
        evaluate_asset(monitored, _ceiling(100.0, 120.0)),
        evaluate_asset(regular, _ceiling(40.0, 50.0)),
    ]

    report = render_dividend_report(decisions, budget=1000.0)
    budget_section = report.split("## Guia de Aporte", maxsplit=1)[1].split(
        "## Ativos monitorados", maxsplit=1
    )[0]

    assert "WATCH" not in budget_section
    assert "REG" in budget_section
    assert "## Ativos monitorados (sem alocacao de budget)" in report

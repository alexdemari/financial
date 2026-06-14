from datetime import datetime


from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.decision import AssetDecision
from dividend_tracker.price_ceiling import PriceCeilingResult
from dividend_tracker.report import render_dividend_report


def _asset(
    ticker: str,
    market: str,
    target_weight: float = 1.0,
    min_dy: float | None = None,
    ceiling_method: str | None = None,
    notes: str | None = None,
) -> DividendAssetConfig:
    return DividendAssetConfig(
        ticker=ticker,
        sector="Energia" if market == "BR" else "ETF",
        name=ticker,
        target_weight=target_weight,
        market=market,
        min_dy=min_dy,
        ceiling_method=ceiling_method,
        notes=notes,
    )


def _decision(
    asset: DividendAssetConfig,
    current_price: float,
    price_ceiling: float,
    min_dy: float = 0.06,
    ceiling_method: str = "trailing",
    current_dy: float = 0.075,
    dividend_base: float = 3.0,
    dividend_base_label: str = "TTM",
    recent_distributions: tuple = (),
) -> AssetDecision:
    ceiling = PriceCeilingResult(
        ticker=asset.ticker,
        price_ceiling=price_ceiling,
        current_dy=current_dy,
        trailing_annual_dividends=dividend_base,
        current_price=current_price,
        margin_pct=(price_ceiling - current_price) / current_price,
        min_dy=min_dy,
        ceiling_method=ceiling_method,
        dividend_base=dividend_base,
        dividend_base_label=dividend_base_label,
        recent_distributions=recent_distributions,
    )
    action = "BUY" if current_price <= price_ceiling else "OVERPRICED"
    return AssetDecision(asset=asset, price_ceiling=ceiling, action=action)


def test_render_dividend_report_includes_summary_and_budget():
    asset = _asset("EGIE3", "BR")
    decision = _decision(asset, current_price=40.0, price_ceiling=50.0)

    report = render_dividend_report(
        [decision],
        budget=8000.0,
        generated_at=datetime(2026, 6, 6, 14, 32),
        processing_errors=["BAD: cache missing"],
    )

    assert "# Relatorio de Dividendos - 06/06/2026 14:32" in report
    assert "## Erros de processamento" in report
    assert "- BAD: cache missing" in report
    assert "| EGIE3 | 100.0% | R$8,000.00 | 200 | <= R$40.00 |" in report


def test_render_dividend_report_marks_custom_min_dy_and_excludes_zero_weight_budget():
    pep_asset = _asset(
        "PEP",
        "US",
        target_weight=0.0,
        min_dy=0.038,
        notes="Operado via venda de puts - IBKR",
    )
    schd_asset = _asset("SCHD", "US", target_weight=1.0)

    decisions = [
        _decision(
            pep_asset,
            current_price=140.68,
            price_ceiling=155.79,
            min_dy=0.038,
            current_dy=0.0421,
            dividend_base=5.92,
        ),
        _decision(
            schd_asset,
            current_price=28.50,
            price_ceiling=26.13,
            min_dy=0.06,
            current_dy=0.0344,
            dividend_base=1.57,
        ),
    ]

    report = render_dividend_report(decisions, budget=1000.0)
    budget_section = report.split("## Guia de Aporte", maxsplit=1)[1].split(
        "## Ativos monitorados", maxsplit=1
    )[0]

    assert (
        "| PEP | ETF | US$140.68 | US$5.92 | TTM | US$155.79 | 4.2% | 3.8% † |"
        in report
    )
    assert "† min_dy customizado por ativo" in report
    assert "PEP" not in budget_section
    assert "## Ativos monitorados (sem alocacao de budget)" in report


def test_render_dividend_report_marks_average_6y_method():
    asset = _asset("EGIE3", "BR", ceiling_method="average_6y")
    decision = _decision(
        asset,
        current_price=40.0,
        price_ceiling=45.0,
        min_dy=0.06,
        ceiling_method="average_6y",
        dividend_base=2.7,
        dividend_base_label="Media 6 anos",
    )

    report = render_dividend_report([decision])

    assert "| EGIE3 | Energia | R$40.00 | R$2.70* | Media 6a | R$45.00 |" in report
    assert "* Dividendo medio anual calculado sobre os ultimos 6 anos" in report


def test_render_dividend_report_buy_and_overpriced_in_summary():
    buy = _asset("BUY1", "BR")
    over = _asset("OVER1", "BR")

    report = render_dividend_report(
        [
            _decision(buy, current_price=40.0, price_ceiling=50.0),
            _decision(over, current_price=60.0, price_ceiling=50.0),
        ]
    )

    assert "- BUY: 1 ativos (BUY1)" in report
    assert "- OVERPRICED: 1 ativos (OVER1)" in report


def test_render_dividend_report_no_technical_columns():
    asset = _asset("EGIE3", "BR")
    decision = _decision(asset, current_price=40.0, price_ceiling=50.0)

    report = render_dividend_report([decision])

    assert "Sinal Tecnico" not in report
    assert "Conviccao" not in report
    assert "WATCH" not in report
    assert "WAIT" not in report

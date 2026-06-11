from datetime import datetime

import pandas as pd

from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.decision import AssetDecision, TechnicalSignalResult
from dividend_tracker.dividend_data import DividendDistribution
from dividend_tracker.price_ceiling import PriceCeilingResult
from dividend_tracker.report import render_dividend_report


def test_render_dividend_report_includes_recent_distributions_and_budget():
    asset = DividendAssetConfig(
        ticker="EGIE3",
        sector="Energia",
        name="Engie",
        target_weight=1.0,
        technical_model="smc",
        market="BR",
    )
    ceiling = PriceCeilingResult(
        ticker="EGIE3",
        price_ceiling=50.0,
        current_dy=0.075,
        trailing_annual_dividends=3.0,
        current_price=40.0,
        margin_pct=0.25,
        recent_distributions=(
            DividendDistribution(date=pd.Timestamp("2026-01-10"), amount=1.0),
            DividendDistribution(date=pd.Timestamp("2026-04-10"), amount=2.0),
        ),
    )
    technical_signal = TechnicalSignalResult(
        signal="BUY",
        model="smc",
        event_type="BUY",
        days_since_event=1,
        interpretation="mock",
    )
    decision = AssetDecision(
        asset=asset,
        price_ceiling=ceiling,
        technical_signal=technical_signal,
        decision="BUY",
        description="Comprar agora",
    )

    report = render_dividend_report(
        [decision],
        budget=8000.0,
        generated_at=datetime(2026, 6, 6, 14, 32),
        processing_errors=["BAD: cache missing"],
    )

    assert "# Relatorio de Dividendos - 06/06/2026 14:32" in report
    assert "2026-01-10: 1.00" in report
    assert "2026-04-10: 2.00" in report
    assert "## Erros de processamento" in report
    assert "- BAD: cache missing" in report
    assert "| EGIE3 | - | 100.0% | 1.0x | R$8,000.00 | 200 | <= R$40.00 |" in report


def test_render_dividend_report_marks_custom_min_dy_and_excludes_zero_weight_budget():
    pep_asset = DividendAssetConfig(
        ticker="PEP",
        sector="Consumer Staples",
        name="PepsiCo",
        target_weight=0.0,
        technical_model="smc",
        market="US",
        min_dy=0.038,
        notes="Operado via venda de puts - IBKR",
    )
    schd_asset = DividendAssetConfig(
        ticker="SCHD",
        sector="ETF Dividendos",
        name="Schwab US Dividend Equity ETF",
        target_weight=1.0,
        technical_model="lux",
        market="US",
    )
    technical_signal = TechnicalSignalResult(
        signal="BUY",
        model="smc",
        event_type="BUY",
        days_since_event=0,
        interpretation="mock",
    )
    decisions = [
        AssetDecision(
            asset=pep_asset,
            price_ceiling=PriceCeilingResult(
                ticker="PEP",
                price_ceiling=155.79,
                current_dy=0.0421,
                trailing_annual_dividends=5.92,
                current_price=140.68,
                margin_pct=0.1074,
                min_dy=0.038,
                ceiling_method="trailing",
                dividend_base=5.92,
            ),
            technical_signal=technical_signal,
            decision="BUY",
            description="Comprar agora",
        ),
        AssetDecision(
            asset=schd_asset,
            price_ceiling=PriceCeilingResult(
                ticker="SCHD",
                price_ceiling=26.13,
                current_dy=0.0344,
                trailing_annual_dividends=1.57,
                current_price=28.50,
                margin_pct=-0.083,
                min_dy=0.06,
                ceiling_method="trailing",
                dividend_base=1.57,
            ),
            technical_signal=technical_signal,
            decision="BUY",
            description="Comprar agora",
        ),
    ]

    report = render_dividend_report(decisions, budget=1000.0)
    budget_section = report.split("## Guia de Aporte", maxsplit=1)[1].split(
        "## Ativos monitorados", maxsplit=1
    )[0]

    assert (
        "| PEP | Consumer Staples | US$140.68 | US$5.92 | TTM | US$155.79 | 4.2% | 3.8% † |"
        in report
    )
    assert "† min_dy customizado por ativo" in report
    assert "PEP" not in budget_section
    assert (
        "| SCHD | - | 100.0% | 1.0x | US$1,000.00 | 35 | <= US$28.50 |"
        in budget_section
    )
    assert "## Ativos monitorados (sem alocacao de budget)" in report
    assert "| PEP | Operado via venda de puts - IBKR | **BUY** |" in report


def test_render_dividend_report_marks_average_6y_method():
    asset = DividendAssetConfig(
        ticker="EGIE3",
        sector="Energia",
        name="Engie",
        target_weight=1.0,
        technical_model="smc",
        market="BR",
        ceiling_method="average_6y",
    )
    technical_signal = TechnicalSignalResult(
        signal="BUY",
        model="smc",
        event_type="BUY",
        days_since_event=0,
        interpretation="mock",
    )
    decision = AssetDecision(
        asset=asset,
        price_ceiling=PriceCeilingResult(
            ticker="EGIE3",
            price_ceiling=45.0,
            current_dy=0.075,
            trailing_annual_dividends=3.0,
            current_price=40.0,
            margin_pct=0.125,
            min_dy=0.06,
            ceiling_method="average_6y",
            dividend_base=2.7,
            dividend_base_label="Media 6 anos",
        ),
        technical_signal=technical_signal,
        decision="BUY",
        description="Comprar agora",
    )

    report = render_dividend_report([decision])

    assert "| EGIE3 | Energia | R$40.00 | R$2.70* | Media 6a | R$45.00 |" in report
    assert "* Dividendo medio anual calculado sobre os ultimos 6 anos" in report

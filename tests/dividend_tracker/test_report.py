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
    assert "| EGIE3 | 100.0% | R$8,000.00 | 200 | <= R$40.00 |" in report

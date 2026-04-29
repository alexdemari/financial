from datetime import UTC, datetime

import pandas as pd

from market_scanner.operational_report import (
    build_asset_ranking,
    build_operational_report,
)


def make_recommendations_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "scope": "global",
                "symbol": None,
                "side": "bullish",
                "recommended_exit_rule": "opposite_signal",
                "qualified": True,
                "qualification_reason": "qualified",
                "ranking_mode": "recent-event",
                "entry_alignment": "bullish_aligned",
                "total_trades": 120,
                "win_rate": 0.62,
                "expectancy": 0.04,
                "profit_factor": 2.1,
                "avg_mfe": 0.12,
                "avg_mae": -0.04,
                "avg_bars_held": 12.0,
                "best_trade": 0.22,
                "worst_trade": -0.08,
            },
            {
                "scope": "symbol",
                "symbol": "AAPL",
                "side": "bullish",
                "recommended_exit_rule": "opposite_signal",
                "qualified": True,
                "qualification_reason": "qualified",
                "ranking_mode": "recent-event",
                "entry_alignment": "bullish_aligned",
                "total_trades": 35,
                "win_rate": 0.60,
                "expectancy": 0.03,
                "profit_factor": 1.8,
                "avg_mfe": 0.11,
                "avg_mae": -0.04,
                "avg_bars_held": 10.0,
                "best_trade": 0.2,
                "worst_trade": -0.12,
            },
            {
                "scope": "symbol",
                "symbol": "AAPL",
                "side": "bearish",
                "recommended_exit_rule": "alignment_break",
                "qualified": True,
                "qualification_reason": "qualified",
                "ranking_mode": "recent-event",
                "entry_alignment": "bearish_aligned",
                "total_trades": 40,
                "win_rate": 0.52,
                "expectancy": 0.01,
                "profit_factor": 1.2,
                "avg_mfe": 0.05,
                "avg_mae": -0.03,
                "avg_bars_held": 5.0,
                "best_trade": 0.1,
                "worst_trade": -0.08,
            },
            {
                "scope": "symbol",
                "symbol": "TSLA",
                "side": "bullish",
                "recommended_exit_rule": "bars_20",
                "qualified": True,
                "qualification_reason": "qualified",
                "ranking_mode": "recent-event",
                "entry_alignment": "bullish_aligned",
                "total_trades": 28,
                "win_rate": 0.57,
                "expectancy": 0.04,
                "profit_factor": 1.9,
                "avg_mfe": 0.18,
                "avg_mae": -0.18,
                "avg_bars_held": 20.0,
                "best_trade": 0.5,
                "worst_trade": -0.2,
            },
        ]
    )


def test_build_asset_ranking_selects_best_side_and_attaches_scan_state():
    scan_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "action_bucket": "candidate",
                "market_state": "pullback",
                "adjusted_alignment": "bullish_aligned",
            }
        ]
    )

    ranking = build_asset_ranking(
        recommendations_df=make_recommendations_df(),
        symbol_comparison_df=pd.DataFrame(),
        scan_df=scan_df,
    )

    aapl = ranking[ranking["symbol"].eq("AAPL")].iloc[0]
    tsla = ranking[ranking["symbol"].eq("TSLA")].iloc[0]

    assert aapl["side"] == "bullish"
    assert aapl["classification"] == "trade_candidate"
    assert aapl["action_bucket"] == "candidate"
    assert tsla["classification"] == "risk_review"


def test_build_operational_report_renders_required_sections():
    report = build_operational_report(
        recommendations_df=make_recommendations_df(),
        symbol_comparison_df=pd.DataFrame(),
        generated_at=datetime(2026, 4, 29, tzinfo=UTC),
        top=10,
    )

    assert "# Execution Operational Report" in report.markdown
    assert "Winning Strategy By Side" in report.markdown
    assert "Asset Classification" in report.markdown
    assert "Symbol Recommendations" in report.markdown
    assert not report.ranking.empty

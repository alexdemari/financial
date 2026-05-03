import pandas as pd

from market_scanner.daily_report import (
    build_qualified_set,
    build_top_candidates,
    filter_fresh_signals,
    infer_side,
    render_daily_report,
)


def _make_scan_row(
    symbol: str,
    action_bucket: str = "candidate",
    adjusted_alignment: str = "bullish_aligned",
    market_state: str = "pullback",
    consistency_score: int = 3,
    lux_days: int | None = None,
    smc_days: int | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "action_bucket": action_bucket,
        "adjusted_alignment": adjusted_alignment,
        "market_state": market_state,
        "consistency_score": consistency_score,
        "lux_days_since_active_event": lux_days,
        "smc_days_since_active_event": smc_days,
        "lux_active_event": "BUY" if lux_days is not None else None,
        "smc_active_event": "OB" if smc_days is not None else None,
    }


def _make_rec_row(
    symbol: str | None,
    side: str,
    scope: str,
    qualified: bool = True,
    recommended_exit_rule: str = "alignment_break",
    expectancy: float = 0.02,
    profit_factor: float = 1.5,
    avg_mae: float = -0.05,
    total_trades: int = 30,
) -> dict:
    row: dict = {
        "scope": scope,
        "side": side,
        "qualified": qualified,
        "recommended_exit_rule": recommended_exit_rule,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "avg_mae": avg_mae,
        "total_trades": total_trades,
    }
    if symbol is not None:
        row["symbol"] = symbol
    else:
        row["symbol"] = None
    return row


def test_filter_fresh_signals_keeps_only_recent_events() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1),
            _make_scan_row("AAPL", lux_days=2),
            _make_scan_row("MSFT", lux_days=5, smc_days=5),
            # TSLA has only an SMC event just above the max_days threshold.
            _make_scan_row("TSLA", smc_days=3),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    symbols = set(fresh["symbol"])
    assert "NVDA" in symbols
    assert "AAPL" in symbols
    assert "MSFT" not in symbols
    assert "TSLA" not in symbols


def test_top_20_requires_candidate_action_bucket() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row("AAPL", "bullish", "symbol"),
            _make_rec_row("NVDA", "bullish", "symbol"),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", action_bucket="candidate", lux_days=1),
            _make_scan_row("AAPL", action_bucket="watchlist", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, recs, top=20)

    assert not top_df.empty
    symbols = set(top_df["symbol"])
    assert "NVDA" in symbols
    assert "AAPL" not in symbols


def test_top_20_cross_references_backtest_qualified() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row("NVDA", "bullish", "symbol", qualified=True),
            _make_rec_row("TSLA", "bullish", "symbol", qualified=False),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1),
            _make_scan_row("TSLA", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, recs, top=20)

    symbols = set(top_df["symbol"]) if not top_df.empty else set()
    assert "NVDA" in symbols
    assert "TSLA" not in symbols


def test_top_20_uses_symbol_recommendation_when_available() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row(
                "NVDA",
                "bullish",
                "symbol",
                recommended_exit_rule="symbol_rule",
                expectancy=0.05,
            ),
            _make_rec_row(
                None,
                "bullish",
                "global",
                recommended_exit_rule="global_rule",
                expectancy=0.01,
            ),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, recs, top=20)

    assert not top_df.empty
    row = top_df[top_df["symbol"] == "NVDA"].iloc[0]
    assert row["recommended_exit_rule"] == "symbol_rule"


def test_top_20_falls_back_to_global_recommendation() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row(
                None,
                "bullish",
                "global",
                recommended_exit_rule="global_rule",
                expectancy=0.03,
            ),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("AAPL", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, recs, top=20)

    assert not top_df.empty
    row = top_df[top_df["symbol"] == "AAPL"].iloc[0]
    assert row["recommended_exit_rule"] == "global_rule"


def test_build_qualified_set_ignores_symbol_scope_without_symbol() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row(None, "bullish", "symbol"),
            _make_rec_row("NVDA", "bullish", "symbol"),
        ]
    )

    symbol_pairs, global_sides, symbols_with_symbol_rec = build_qualified_set(recs)

    assert (None, "bullish") not in symbol_pairs
    assert ("NVDA", "bullish") in symbol_pairs
    assert global_sides == set()
    assert symbols_with_symbol_rec == {"NVDA"}


def test_infer_side_from_adjusted_alignment() -> None:
    assert infer_side("bullish_aligned") == "bullish"
    assert infer_side("bearish_aligned") == "bearish"
    assert infer_side("no_trade") is None
    assert infer_side("mixed") is None


def test_render_markdown_contains_required_sections() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1),
            _make_scan_row("AAPL", action_bucket="watchlist", lux_days=5),
        ]
    )
    recs = pd.DataFrame(
        [
            _make_rec_row("NVDA", "bullish", "symbol"),
        ]
    )
    md = render_daily_report(scan_df, recs, max_days=2, top=20)

    assert "Sinais Frescos" in md
    assert "Top 20 Operacional" in md
    assert "Sumário por Bucket" in md
    assert "Stats" in md


def test_render_stats_counts_qualified_before_top_cap() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1, consistency_score=10),
            _make_scan_row("AAPL", lux_days=1, consistency_score=9),
            _make_scan_row("MSFT", lux_days=1, consistency_score=8),
        ]
    )
    recs = pd.DataFrame(
        [
            _make_rec_row("NVDA", "bullish", "symbol"),
            _make_rec_row("AAPL", "bullish", "symbol"),
            _make_rec_row("MSFT", "bullish", "symbol"),
        ]
    )
    md = render_daily_report(scan_df, recs, max_days=2, top=2)

    assert "- Qualificados pelo backtest: 3" in md
    assert "- No Top 2: 2" in md


def test_render_stats_labels_candidates_when_recommendations_absent() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1, consistency_score=10),
            _make_scan_row("AAPL", lux_days=1, consistency_score=9),
            _make_scan_row("MSFT", action_bucket="watchlist", lux_days=1),
        ]
    )
    md = render_daily_report(scan_df, recommendations_df=None, max_days=2, top=1)

    assert "- Candidatos frescos (sem filtro backtest): 2" in md
    assert "- Qualificados pelo backtest:" not in md
    assert "- No Top 1: 1" in md

import pandas as pd

from market_scanner.daily_report import (
    RankingStrategy,
    build_qualified_set,
    build_top_candidates,
    filter_fresh_signals,
    infer_side,
    render_daily_report,
    write_daily_report,
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


def test_top_20_lux_strategy_includes_all_buckets() -> None:
    """Pool now includes all buckets; lux strategy filters by lux freshness."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", action_bucket="candidate", lux_days=1),
            _make_scan_row("AAPL", action_bucket="watchlist", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.lux)

    assert not top_df.empty
    symbols = set(top_df["symbol"])
    # Both are lux-fresh, so both should appear
    assert "NVDA" in symbols
    assert "AAPL" in symbols


def test_top_20_cross_references_backtest_qualified() -> None:
    """Backtest integration is Feature C; for now, no backtest filter applied."""
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
    # No backtest filter in this feature; both lux-fresh symbols appear
    top_df = build_top_candidates(fresh, recs, top=20, strategy=RankingStrategy.lux)

    symbols = set(top_df["symbol"]) if not top_df.empty else set()
    assert "NVDA" in symbols
    # TSLA is lux-fresh and backtest filter is not applied, so it now appears
    assert "TSLA" in symbols


def test_top_20_uses_symbol_recommendation_when_available() -> None:
    """Backtest metrics are Feature C; rec columns are NA in current feature."""
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
    top_df = build_top_candidates(fresh, recs, top=20, strategy=RankingStrategy.lux)

    assert not top_df.empty
    # Backtest filter not applied; NVDA appears but rec metrics are NA
    row = top_df[top_df["symbol"] == "NVDA"].iloc[0]
    assert pd.isna(row["recommended_exit_rule"])


def test_top_20_falls_back_to_global_recommendation() -> None:
    """Backtest metrics are Feature C; rec columns are NA in current feature."""
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
    top_df = build_top_candidates(fresh, recs, top=20, strategy=RankingStrategy.lux)

    assert not top_df.empty
    row = top_df[top_df["symbol"] == "AAPL"].iloc[0]
    # Backtest metrics not populated in this feature
    assert pd.isna(row["recommended_exit_rule"])


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
    # With all strategies: LUX, SMC, DUAL sections
    assert "LUX" in md
    assert "SMC" in md
    assert "DUAL" in md
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

    # Stats now shows fresh counts per strategy, not backtest qualified count
    assert "Frescos LUX" in md
    assert "- No Top" not in md


def test_render_stats_labels_candidates_when_recommendations_absent() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1, consistency_score=10),
            _make_scan_row("AAPL", lux_days=1, consistency_score=9),
            _make_scan_row("MSFT", action_bucket="watchlist", lux_days=1),
        ]
    )
    md = render_daily_report(scan_df, recommendations_df=None, max_days=2, top=1)

    # Stats now shows fresh signal counts per strategy
    assert "Frescos LUX" in md
    assert "- Qualificados pelo backtest:" not in md


def test_fresh_signals_section_shows_only_candidates() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", action_bucket="candidate", lux_days=1),
            _make_scan_row("AAPL", action_bucket="watchlist", lux_days=1),
        ]
    )
    md = render_daily_report(scan_df, None, max_days=2, top=20)

    # Section 1 header unchanged
    assert "Sinais Frescos — Candidates" in md
    # NVDA is candidate — shown in section 1
    assert "NVDA" in md
    # AAPL is watchlist — excluded from section 1 (fresh candidates table)
    fresh_section = md.split("## 2.")[0]
    assert "AAPL" not in fresh_section
    # Stats still counts both in total fresh, but candidates fresh = 1
    assert "- Com sinal fresco" in md
    assert "- Candidates frescos: 1" in md


def test_global_rec_source_shown_in_top_20() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row(None, "bullish", "global", total_trades=147396),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("BTBT", action_bucket="candidate", lux_days=1),
        ]
    )
    md = render_daily_report(scan_df, recs, max_days=2, top=20)

    # BTBT appears in the LUX section (lux-fresh)
    assert "BTBT" in md
    # Backtest metrics are not applied; large aggregate number not shown
    assert "147396" not in md


def test_symbol_rec_source_shown_in_top_20() -> None:
    recs = pd.DataFrame(
        [
            _make_rec_row("NVDA", "bullish", "symbol", total_trades=30),
        ]
    )
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", action_bucket="candidate", lux_days=1),
        ]
    )
    md = render_daily_report(scan_df, recs, max_days=2, top=20)

    # NVDA appears; backtest metrics not applied so "30" won't appear
    assert "NVDA" in md


def test_smc_fresh_candidates_rank_above_lux_only() -> None:
    # Under SMC strategy: DUAL has smc_days=1, LUX_ONLY has smc_days=10 (excluded)
    scan_df = pd.DataFrame(
        [
            _make_scan_row("LUX_ONLY", lux_days=1, smc_days=10, consistency_score=5),
            _make_scan_row("DUAL", lux_days=1, smc_days=1, consistency_score=5),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(
        fresh, None, top=20, max_days=2, strategy=RankingStrategy.smc
    )

    assert not top_df.empty
    # Only DUAL has smc_days <= 2
    symbols = set(top_df["symbol"])
    assert "DUAL" in symbols
    assert "LUX_ONLY" not in symbols


def test_consistency_score_breaks_tie_within_smc_fresh_group() -> None:
    scan_df = pd.DataFrame(
        [
            _make_scan_row("HIGH", lux_days=1, smc_days=1, consistency_score=8),
            _make_scan_row("LOW", lux_days=1, smc_days=2, consistency_score=3),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(
        fresh, None, top=20, max_days=2, strategy=RankingStrategy.smc
    )

    # Both are smc-fresh; HIGH has lower smc_days (1 < 2) so ranks first
    assert top_df.iloc[0]["symbol"] == "HIGH"
    assert top_df.iloc[1]["symbol"] == "LOW"


def test_archive_dir_creates_dated_copy(tmp_path) -> None:
    from datetime import datetime

    scan_df = pd.DataFrame([_make_scan_row("NVDA", lux_days=1)])
    scan_csv = tmp_path / "scan.csv"
    scan_df.to_csv(scan_csv, index=False)

    output_md = tmp_path / "daily_report.md"
    archive_dir = tmp_path / "archive"

    report = write_daily_report(
        scan_path=scan_csv,
        output_path=output_md,
        archive_dir=archive_dir,
    )

    date_str = datetime.now().strftime("%Y-%m-%d")
    dated_md = archive_dir / f"{date_str}.md"

    assert dated_md.exists(), f"Expected dated copy at {dated_md}"
    assert dated_md.read_text(encoding="utf-8") == report
    assert dated_md.read_text(encoding="utf-8") == output_md.read_text(encoding="utf-8")


def test_archive_dir_copies_candidates_csv_when_provided(tmp_path) -> None:
    from datetime import datetime

    scan_df = pd.DataFrame([_make_scan_row("NVDA", lux_days=1)])
    scan_csv = tmp_path / "scan.csv"
    scan_df.to_csv(scan_csv, index=False)

    candidates_csv = tmp_path / "candidates.csv"
    scan_df.to_csv(candidates_csv, index=False)

    output_md = tmp_path / "daily_report.md"
    archive_dir = tmp_path / "archive"

    write_daily_report(
        scan_path=scan_csv,
        output_path=output_md,
        output_candidates=candidates_csv,
        archive_dir=archive_dir,
    )

    date_str = datetime.now().strftime("%Y-%m-%d")
    dated_csv = archive_dir / f"{date_str}_candidates.csv"
    assert dated_csv.exists(), f"Expected dated candidates at {dated_csv}"


def test_archive_dir_absent_preserves_original_behavior(tmp_path) -> None:
    scan_df = pd.DataFrame([_make_scan_row("NVDA", lux_days=1)])
    scan_csv = tmp_path / "scan.csv"
    scan_df.to_csv(scan_csv, index=False)

    output_md = tmp_path / "daily_report.md"

    report = write_daily_report(
        scan_path=scan_csv,
        output_path=output_md,
    )

    assert output_md.exists()
    assert "Daily Report" in report
    assert not (tmp_path / "archive").exists()


# ---------------------------------------------------------------------------
# New tests — Feature A: multi-strategy rankings
# ---------------------------------------------------------------------------


def test_lux_strategy_sorts_by_lux_days_asc() -> None:
    """AAPL(lux_days=1) ranks above NVDA(lux_days=2) under lux strategy."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=2, consistency_score=5),
            _make_scan_row("AAPL", lux_days=1, consistency_score=5),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.lux)

    assert not top_df.empty
    assert top_df.iloc[0]["symbol"] == "AAPL"
    assert top_df.iloc[1]["symbol"] == "NVDA"


def test_smc_strategy_sorts_by_smc_days_asc() -> None:
    """AAPL(smc_days=1) ranks above NVDA(smc_days=2) under smc strategy."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", smc_days=2, consistency_score=5),
            _make_scan_row("AAPL", smc_days=1, consistency_score=5),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.smc)

    assert not top_df.empty
    assert top_df.iloc[0]["symbol"] == "AAPL"
    assert top_df.iloc[1]["symbol"] == "NVDA"


def test_dual_strategy_requires_both_fresh() -> None:
    """Symbol with only lux fresh or only smc fresh is excluded from dual."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("LUX_ONLY", lux_days=1, smc_days=None, consistency_score=5),
            _make_scan_row("SMC_ONLY", lux_days=None, smc_days=1, consistency_score=5),
            _make_scan_row("BOTH", lux_days=1, smc_days=1, consistency_score=5),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.dual)

    symbols = set(top_df["symbol"]) if not top_df.empty else set()
    assert "BOTH" in symbols
    assert "LUX_ONLY" not in symbols
    assert "SMC_ONLY" not in symbols


def test_pool_includes_watchlist_with_fresh_signal() -> None:
    """Watchlist symbol with lux_days=1 appears in lux ranking (all buckets in pool)."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("WATCH_SYM", action_bucket="watchlist", lux_days=1),
            _make_scan_row("CAND_SYM", action_bucket="candidate", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.lux)

    symbols = set(top_df["symbol"])
    assert "WATCH_SYM" in symbols
    assert "CAND_SYM" in symbols


def test_action_bucket_visible_in_output() -> None:
    """action_bucket column must be present in top_df."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", action_bucket="candidate", lux_days=1),
        ]
    )
    fresh = filter_fresh_signals(scan_df, max_days=2)
    top_df = build_top_candidates(fresh, None, top=20, strategy=RankingStrategy.lux)

    assert not top_df.empty
    assert "action_bucket" in top_df.columns


def test_strategy_all_renders_three_sections() -> None:
    """Rendered MD contains LUX, SMC, and DUAL section headers when strategy=None."""
    scan_df = pd.DataFrame(
        [
            _make_scan_row("NVDA", lux_days=1, smc_days=1),
            _make_scan_row("AAPL", lux_days=2, smc_days=2),
        ]
    )
    md = render_daily_report(scan_df, None, max_days=2, top=20, strategy=None)

    assert "— LUX" in md
    assert "— SMC" in md
    assert "— DUAL" in md

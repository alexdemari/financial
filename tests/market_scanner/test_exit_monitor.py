"""Tests for exit_monitor.py — position evaluation against scan output."""

from datetime import date

import pandas as pd

from market_scanner.exit_monitor import (
    EXIT_STATUS_EXIT,
    EXIT_STATUS_HOLD,
    EXIT_STATUS_WATCH,
    evaluate_positions,
)
from market_scanner.portfolio import Position


def _make_position(
    symbol="AAPL",
    side="bullish",
    entry_date=date(2026, 5, 1),
    option_type="put",
    option_direction="short",
    option_strike=50.0,
    option_expiry=date(2026, 6, 18),
    premium_paid=1.45,
    contracts=1,
    delta=-0.25,
    iv=25.0,
    signal_source="lux",
    recommended_exit_rule="alignment_break",
) -> Position:
    return Position(
        symbol=symbol,
        side=side,
        entry_date=entry_date,
        option_type=option_type,
        option_direction=option_direction,
        option_strike=option_strike,
        option_expiry=option_expiry,
        premium_paid=premium_paid,
        contracts=contracts,
        delta=delta,
        iv=iv,
        signal_source=signal_source,
        recommended_exit_rule=recommended_exit_rule,
    )


def _make_scan_row(
    symbol="AAPL",
    adjusted_alignment="bullish_aligned",
    action_bucket="candidate",
    market_state="trending",
) -> dict:
    return {
        "symbol": symbol,
        "adjusted_alignment": adjusted_alignment,
        "action_bucket": action_bucket,
        "market_state": market_state,
    }


def _scan_df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ---------------------------------------------------------------------------
# alignment_break rule
# ---------------------------------------------------------------------------


def test_exit_on_alignment_break_fires():
    pos = _make_position(side="bullish", recommended_exit_rule="alignment_break")
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bearish_aligned"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "alignment_break" in result.iloc[0]["exit_reason"]


def test_hold_when_alignment_intact():
    pos = _make_position(side="bullish", recommended_exit_rule="alignment_break")
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_HOLD


# ---------------------------------------------------------------------------
# bucket_downgrade rule
# ---------------------------------------------------------------------------


def test_exit_on_bucket_downgrade():
    pos = _make_position(recommended_exit_rule="bucket_downgrade")
    scan = _scan_df(_make_scan_row(symbol="AAPL", action_bucket="avoid"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "bucket_downgrade" in result.iloc[0]["exit_reason"]


def test_watch_on_bucket_watchlist():
    pos = _make_position(recommended_exit_rule="bucket_downgrade")
    scan = _scan_df(_make_scan_row(symbol="AAPL", action_bucket="watchlist"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_WATCH
    assert "watchlist" in result.iloc[0]["exit_reason"]


# ---------------------------------------------------------------------------
# bars_N rule
# ---------------------------------------------------------------------------


def test_exit_on_bars_n():
    pos = _make_position(
        entry_date=date(2026, 5, 1),
        recommended_exit_rule="bars_5",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL"))
    # 9 days held → ≥ 5 → EXIT
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "bars_5" in result.iloc[0]["exit_reason"]


def test_watch_approaching_bars_n():
    pos = _make_position(
        entry_date=date(2026, 5, 1),
        recommended_exit_rule="bars_5",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL"))
    # 4 days held → ≥ 5-2=3 but < 5 → WATCH
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 5))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_WATCH


def test_hold_below_watch_buffer_bars_n():
    pos = _make_position(
        entry_date=date(2026, 5, 1),
        recommended_exit_rule="bars_10",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL"))
    # 2 days held → < 10-2=8 → HOLD
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 3))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_HOLD


def test_watch_when_bars_n_entry_date_is_unavailable(caplog):
    pos = _make_position(entry_date=None, recommended_exit_rule="bars_5")
    scan = _scan_df(_make_scan_row(symbol="AAPL"))

    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))

    assert result.iloc[0]["exit_status"] == EXIT_STATUS_WATCH
    assert result.iloc[0]["days_held"] is None
    assert result.iloc[0]["entry_date"] == ""
    assert "entry date unavailable" in result.iloc[0]["exit_reason"]
    assert "entry date unavailable" in caplog.text


# ---------------------------------------------------------------------------
# Symbol not in scan
# ---------------------------------------------------------------------------


def test_watch_when_symbol_not_in_scan():
    pos = _make_position(symbol="AAPL", recommended_exit_rule="alignment_break")
    scan = _scan_df(_make_scan_row(symbol="MSFT"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_WATCH
    assert "not in scan" in result.iloc[0]["exit_reason"]


# ---------------------------------------------------------------------------
# Sort order
# ---------------------------------------------------------------------------


def test_sorts_exit_first_watch_second_hold_last():
    pos_hold = _make_position(
        symbol="AAPL", side="bullish", recommended_exit_rule="alignment_break"
    )
    pos_watch = _make_position(
        symbol="GOOG", recommended_exit_rule="alignment_break"
    )  # not in scan → WATCH
    pos_exit = _make_position(
        symbol="MSFT", side="bullish", recommended_exit_rule="alignment_break"
    )

    scan = _scan_df(
        _make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"),
        _make_scan_row(symbol="MSFT", adjusted_alignment="bearish_aligned"),
    )
    result = evaluate_positions(
        [pos_hold, pos_watch, pos_exit], scan, as_of_date=date(2026, 5, 10)
    )
    statuses = result["exit_status"].tolist()
    assert statuses[0] == EXIT_STATUS_EXIT
    assert statuses[1] == EXIT_STATUS_WATCH
    assert statuses[2] == EXIT_STATUS_HOLD


# ---------------------------------------------------------------------------
# Recommendations override
# ---------------------------------------------------------------------------


def test_recs_lookup_overrides_position_exit_rule():
    # Position has alignment_break, but recs say bars_5
    pos = _make_position(
        symbol="AAPL",
        side="bullish",
        entry_date=date(2026, 5, 1),
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    recs = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "side": "bullish",
                "qualified": True,
                "recommended_exit_rule": "bars_5",
            },
        ]
    )
    # 9 days held — alignment intact but bars_5 should fire
    result = evaluate_positions([pos], scan, recs, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert result.iloc[0]["recommended_exit_rule"] == "bars_5"


def test_recs_lookup_ignores_unqualified_rows():
    pos = _make_position(
        symbol="AAPL",
        side="bullish",
        entry_date=date(2026, 5, 1),
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    recs = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "side": "bullish",
                "qualified": False,
                "recommended_exit_rule": "bars_5",
            },
        ]
    )
    result = evaluate_positions([pos], scan, recs, as_of_date=date(2026, 5, 10))
    # Should fall back to alignment_break → HOLD (alignment intact)
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_HOLD
    assert result.iloc[0]["recommended_exit_rule"] == "alignment_break"


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


def test_empty_positions_returns_empty_df():
    result = evaluate_positions([], pd.DataFrame(), as_of_date=date(2026, 5, 10))
    assert result.empty


def test_late_state_rule_fires():
    pos = _make_position(recommended_exit_rule="late_state")
    scan = _scan_df(_make_scan_row(symbol="AAPL", market_state="exhaustion"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "late_state" in result.iloc[0]["exit_reason"]


def test_opposite_signal_rule_fires():
    pos = _make_position(side="bullish", recommended_exit_rule="opposite_signal")
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bearish_aligned"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "opposite_signal" in result.iloc[0]["exit_reason"]


# ---------------------------------------------------------------------------
# DTE alerts
# ---------------------------------------------------------------------------


def test_dte_exit_fires_within_exit_threshold():
    pos = _make_position(
        option_expiry=date(2026, 5, 15),  # 5 days from as_of → ≤ 7
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    result = evaluate_positions(
        [pos], scan, as_of_date=date(2026, 5, 10), dte_exit_days=7, dte_watch_days=14
    )
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT
    assert "DTE" in result.iloc[0]["exit_reason"]


def test_dte_watch_fires_within_watch_threshold():
    pos = _make_position(
        option_expiry=date(2026, 5, 20),  # 10 days → ≤ 14 but > 7
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    result = evaluate_positions(
        [pos], scan, as_of_date=date(2026, 5, 10), dte_exit_days=7, dte_watch_days=14
    )
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_WATCH
    assert "DTE" in result.iloc[0]["exit_reason"]


def test_dte_hold_when_far_expiry():
    pos = _make_position(
        option_expiry=date(2026, 8, 20),  # 100+ days → no DTE trigger
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    result = evaluate_positions(
        [pos], scan, as_of_date=date(2026, 5, 10), dte_exit_days=7, dte_watch_days=14
    )
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_HOLD


def test_dte_exit_overrides_hold_from_rule():
    # alignment_break rule → HOLD (alignment intact), but DTE ≤ 7 → EXIT wins
    pos = _make_position(
        option_expiry=date(2026, 5, 14),  # 4 days → EXIT
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    result = evaluate_positions(
        [pos], scan, as_of_date=date(2026, 5, 10), dte_exit_days=7, dte_watch_days=14
    )
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT


def test_dte_column_present_in_result():
    pos = _make_position(option_expiry=date(2026, 8, 1))
    scan = _scan_df(_make_scan_row(symbol="AAPL"))
    result = evaluate_positions([pos], scan, as_of_date=date(2026, 5, 10))
    assert "dte" in result.columns
    assert result.iloc[0]["dte"] == (date(2026, 8, 1) - date(2026, 5, 10)).days


def test_dte_configurable_thresholds():
    pos = _make_position(
        option_expiry=date(2026, 5, 20),  # 10 days
        recommended_exit_rule="alignment_break",
    )
    scan = _scan_df(_make_scan_row(symbol="AAPL", adjusted_alignment="bullish_aligned"))
    # With tight thresholds: exit=15, watch=20 → 10 days = EXIT
    result = evaluate_positions(
        [pos], scan, as_of_date=date(2026, 5, 10), dte_exit_days=15, dte_watch_days=20
    )
    assert result.iloc[0]["exit_status"] == EXIT_STATUS_EXIT

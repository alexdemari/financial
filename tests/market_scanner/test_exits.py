from market_scanner.exits import (
    exit_after_n_bars,
    exit_on_alignment_break,
    exit_on_bucket_downgrade,
    exit_on_late_state,
    exit_on_opposite_signal,
)


def test_exit_on_alignment_break_for_bullish_and_bearish():
    assert (
        exit_on_alignment_break(
            {"adjusted_alignment": "bullish_aligned"},
            "bullish",
        )
        is False
    )
    assert (
        exit_on_alignment_break(
            {"adjusted_alignment": "bearish_aligned"},
            "bullish",
        )
        is True
    )
    assert (
        exit_on_alignment_break(
            {"adjusted_alignment": "bearish_aligned"},
            "bearish",
        )
        is False
    )
    assert (
        exit_on_alignment_break(
            {"adjusted_alignment": "bullish_aligned"},
            "bearish",
        )
        is True
    )


def test_exit_on_bucket_downgrade():
    assert exit_on_bucket_downgrade({"action_bucket": "watchlist"}) is True
    assert exit_on_bucket_downgrade({"action_bucket": "avoid"}) is True
    assert exit_on_bucket_downgrade({"action_bucket": "needs_review"}) is True
    assert exit_on_bucket_downgrade({"action_bucket": "candidate"}) is False


def test_exit_on_late_state():
    assert exit_on_late_state({"market_state": "extended"}) is True
    assert exit_on_late_state({"market_state": "exhaustion"}) is True
    assert exit_on_late_state({"market_state": "pullback"}) is False


def test_exit_on_opposite_signal():
    assert (
        exit_on_opposite_signal(
            {"adjusted_alignment": "bearish_aligned"},
            "bullish",
        )
        is True
    )
    assert (
        exit_on_opposite_signal(
            {"adjusted_alignment": "bullish_aligned"},
            "bullish",
        )
        is False
    )
    assert (
        exit_on_opposite_signal(
            {"adjusted_alignment": "bullish_aligned"},
            "bearish",
        )
        is True
    )


def test_exit_after_n_bars():
    assert exit_after_n_bars(4, 5) is False
    assert exit_after_n_bars(5, 5) is True
    assert exit_after_n_bars(6, 5) is True

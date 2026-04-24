from options_tech_scanner.market_state import (
    EXHAUSTION,
    EXTENDED,
    PULLBACK,
    RANGE,
    UNKNOWN,
    adjust_alignment_for_market_state,
    classify_action_bucket,
    classify_market_state,
)


def test_afrm_like_case_becomes_bullish_watchlist():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 78,
        "smc_rsi": 65,
        "alignment": "bullish_aligned",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state in {EXTENDED, EXHAUSTION}
    assert adjusted_alignment == "bullish_watchlist"
    assert action_bucket == "watchlist"


def test_gild_like_case_keeps_bearish_bias_but_not_clean_entry():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 3,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 9,
        "smc_rsi": 36,
        "alignment": "mixed",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state in {EXTENDED, EXHAUSTION}
    assert adjusted_alignment in {"bearish_aligned", "bearish_watchlist"}
    assert action_bucket in {"candidate", "watchlist"}


def test_nu_like_case_is_not_promoted_to_bullish_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 0,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 23,
        "smc_rsi": 44,
        "alignment": "mixed",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state in {RANGE, PULLBACK, UNKNOWN}
    assert adjusted_alignment != "bullish_aligned"
    assert action_bucket in {"watchlist", "avoid", "needs_review"}


def test_missing_numeric_values_return_unknown_market_state():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "smc_bias": "NEUTRAL",
        "alignment": "bullish_aligned",
    }

    assert classify_market_state(row) == UNKNOWN


def test_invalid_numeric_values_return_unknown_market_state():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": "not-a-number",
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": "bad-value",
        "smc_rsi": "",
        "alignment": "bullish_aligned",
    }

    assert classify_market_state(row) == UNKNOWN


def test_range_case_becomes_range_watchlist():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "HOLD",
        "lux_days_since_last_event": 20,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 50,
        "smc_rsi": 50,
        "alignment": "mixed",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state == RANGE
    assert adjusted_alignment == "range_watchlist"
    assert action_bucket == "watchlist"


def test_clean_bullish_candidate_stays_candidate():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": 3,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 52,
        "alignment": "bullish_aligned",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state in {"early_trend", "pullback"}
    assert adjusted_alignment == "bullish_aligned"
    assert action_bucket == "candidate"


def test_clean_bearish_candidate_stays_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "STRONG",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 48,
        "alignment": "bearish_aligned",
    }

    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=row["alignment"],
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(adjusted_alignment, market_state)

    assert market_state in {"early_trend", "pullback"}
    assert adjusted_alignment == "bearish_aligned"
    assert action_bucket == "candidate"

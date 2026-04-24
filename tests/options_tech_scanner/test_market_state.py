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


def _evaluate(row: dict[str, object]) -> tuple[str, str, str]:
    market_state = classify_market_state(row)
    adjusted_alignment = adjust_alignment_for_market_state(
        alignment=str(row["alignment"]),
        row=row,
        market_state=market_state,
    )
    action_bucket = classify_action_bucket(
        adjusted_alignment,
        market_state,
        consistency_score=row.get("consistency_score"),
    )
    return market_state, adjusted_alignment, action_bucket


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
        "consistency_score": 1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

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
        "consistency_score": 1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state in {EXTENDED, EXHAUSTION}
    assert adjusted_alignment == "bearish_watchlist"
    assert action_bucket == "watchlist"


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
        "consistency_score": 0,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state in {RANGE, PULLBACK, UNKNOWN}
    assert adjusted_alignment != "bullish_aligned"
    assert action_bucket in {"watchlist", "avoid", "needs_review"}


def test_baba_like_case_becomes_bearish_watchlist_not_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 0,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 29.13,
        "smc_rsi": 48.44,
        "alignment": "mixed",
        "consistency_score": -1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == RANGE
    assert adjusted_alignment == "bearish_watchlist"
    assert action_bucket == "watchlist"


def test_ccl_like_case_becomes_range_watchlist_not_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 1,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 31.41,
        "smc_rsi": 47.20,
        "alignment": "mixed",
        "consistency_score": -1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == RANGE
    assert adjusted_alignment == "bearish_watchlist"
    assert action_bucket == "watchlist"


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
        "consistency_score": 0,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == RANGE
    assert adjusted_alignment == "range_watchlist"
    assert action_bucket == "watchlist"


def test_clean_bullish_candidate_is_pullback_candidate():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": 3,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 52,
        "alignment": "bullish_aligned",
        "consistency_score": 4,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bullish_aligned"
    assert action_bucket == "candidate"


def test_strong_bearish_pullback_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "STRONG",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 50,
        "alignment": "bearish_aligned",
        "consistency_score": 1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bearish_aligned"
    assert action_bucket == "candidate"


def test_mixed_strong_bearish_pullback_candidate():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "STRONG",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 50,
        "alignment": "mixed",
        "consistency_score": 1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bearish_aligned"
    assert action_bucket == "candidate"


def test_mixed_normal_bearish_pullback_stays_watchlist():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 50,
        "alignment": "mixed",
        "consistency_score": 0,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bearish_watchlist"
    assert action_bucket == "watchlist"


def test_mixed_strong_bullish_pullback_candidate():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 50,
        "smc_rsi": 54,
        "alignment": "mixed",
        "consistency_score": 1,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bullish_aligned"
    assert action_bucket == "candidate"


def test_mixed_normal_bullish_pullback_stays_watchlist():
    row = {
        "lux_trend": "BULLISH",
        "lux_strength": "NORMAL",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 50,
        "smc_rsi": 54,
        "alignment": "mixed",
        "consistency_score": 0,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bullish_watchlist"
    assert action_bucket == "watchlist"


def test_aligned_pullback_with_zero_consistency_becomes_watchlist():
    row = {
        "lux_trend": "BEARISH",
        "lux_strength": "STRONG",
        "lux_last_event": "SELL",
        "lux_days_since_last_event": 2,
        "smc_bias": "NEUTRAL",
        "smc_range_position_pct": 55,
        "smc_rsi": 50,
        "alignment": "bearish_aligned",
        "consistency_score": 0,
    }

    market_state, adjusted_alignment, action_bucket = _evaluate(row)

    assert market_state == PULLBACK
    assert adjusted_alignment == "bearish_aligned"
    assert action_bucket == "watchlist"

from market_scanner.ranking import (
    classify_alignment,
    compute_consistency_score,
    infer_lux_role,
    infer_smc_role,
)


def test_classify_alignment_bullish_and_bearish():
    assert classify_alignment("bullish_trigger", "bullish_watch") == "bullish_watch"
    assert classify_alignment("bearish_trigger", "bearish_watch") == "bearish_watch"
    assert classify_alignment("neutral", "neutral") == "no_trade"
    assert classify_alignment("bullish_trend", "bearish_trigger") == "conflicted"


def test_infer_roles_reflect_asymmetric_model():
    assert (
        infer_lux_role(
            lux_signal="BUY",
            lux_options_hint="CALL",
            lux_trend="BULLISH",
        )
        == "bullish_trigger"
    )
    assert (
        infer_smc_role(
            smc_signal="HOLD",
            smc_options_hint="CALL_WATCH",
            smc_context="short_term_bullish_reversal",
            smc_bias="NEUTRAL",
        )
        == "bullish_trigger"
    )


def test_compute_consistency_score_weights_smc_trigger_and_conflict():
    assert (
        compute_consistency_score(
            lux_role="bullish_trigger",
            smc_role="bullish_trigger",
            lux_signal="BUY",
            smc_signal="BUY",
        )
        == 6
    )
    assert (
        compute_consistency_score(
            lux_role="bullish_trend",
            smc_role="bullish_watch",
            lux_signal="BUY",
            smc_signal="HOLD",
        )
        == 3
    )
    assert (
        compute_consistency_score(
            lux_role="bullish_trend",
            smc_role="bearish_watch",
            lux_signal="BUY",
            smc_signal="SELL",
        )
        == -2
    )

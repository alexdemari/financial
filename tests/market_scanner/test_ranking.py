from market_scanner.ranking import classify_alignment, compute_consistency_score


def test_classify_alignment_bullish_and_bearish():
    assert classify_alignment("CALL", "CALL_WATCH") == "bullish_aligned"
    assert classify_alignment("PUT", "PUT_WATCH") == "bearish_aligned"
    assert classify_alignment("NO_TRADE", "NO_TRADE") == "no_trade"
    assert classify_alignment("CALL", "PUT") == "mixed"


def test_compute_consistency_score_matches_v1_rules():
    assert (
        compute_consistency_score(
            lux_options_hint="CALL",
            smc_options_hint="CALL",
            lux_signal="BUY",
            smc_signal="BUY",
        )
        == 4
    )
    assert (
        compute_consistency_score(
            lux_options_hint="CALL",
            smc_options_hint="CALL_WATCH",
            lux_signal="BUY",
            smc_signal="HOLD",
        )
        == 1
    )
    assert (
        compute_consistency_score(
            lux_options_hint="CALL",
            smc_options_hint="PUT_WATCH",
            lux_signal="BUY",
            smc_signal="SELL",
        )
        == -1
    )

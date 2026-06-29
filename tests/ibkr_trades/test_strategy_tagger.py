"""Tests for strategy_tagger.py"""

from ibkr_trades.strategy_tagger import infer_strategy


def test_strategy_tagger_covered_call():
    row = {
        "asset_type": "OPT",
        "quantity": -1,
        "option_type": "CALL",
        "open_close": "O",
    }
    assert infer_strategy(row) == "covered_call"


def test_strategy_tagger_csp():
    row = {"asset_type": "OPT", "quantity": -1, "option_type": "PUT", "open_close": "O"}
    assert infer_strategy(row) == "csp"


def test_strategy_tagger_long_call():
    row = {"asset_type": "OPT", "quantity": 1, "option_type": "CALL", "open_close": "O"}
    assert infer_strategy(row) == "long_call"


def test_strategy_tagger_long_put():
    row = {"asset_type": "OPT", "quantity": 1, "option_type": "PUT", "open_close": "O"}
    assert infer_strategy(row) == "long_put"


def test_strategy_tagger_roll_takes_precedence():
    row = {
        "asset_type": "OPT",
        "quantity": -1,
        "option_type": "PUT",
        "open_close": "O",
        "roll_id": "some-uuid",
    }
    assert infer_strategy(row) == "roll"


def test_strategy_tagger_closing_trade_returns_none():
    row = {"asset_type": "OPT", "quantity": 1, "option_type": "PUT", "open_close": "C"}
    assert infer_strategy(row) is None


def test_strategy_tagger_stk_returns_none():
    row = {"asset_type": "STK", "quantity": 10, "option_type": None, "open_close": "O"}
    assert infer_strategy(row) is None


def test_strategy_tagger_nan_roll_id_not_treated_as_roll():
    # After CSV round-trip, empty roll_id becomes float NaN — must not match "roll"
    row = {
        "asset_type": "OPT",
        "quantity": -1,
        "option_type": "PUT",
        "open_close": "O",
        "roll_id": float("nan"),
    }
    assert infer_strategy(row) == "csp"

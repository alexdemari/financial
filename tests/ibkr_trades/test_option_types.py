"""Tests for option_types.py"""

import math

from ibkr_trades.option_types import normalize_option_type


def test_normalize_option_type_c_to_call():
    assert normalize_option_type("C") == "CALL"


def test_normalize_option_type_p_to_put():
    assert normalize_option_type("p") == "PUT"


def test_normalize_option_type_passthrough_already_normalized():
    assert normalize_option_type("CALL") == "CALL"
    assert normalize_option_type("PUT") == "PUT"


def test_normalize_option_type_none_input():
    assert normalize_option_type(None) is None


def test_normalize_option_type_nan_input():
    assert normalize_option_type(float("nan")) is None
    assert math.isnan(float("nan"))  # sanity check on the input itself


def test_normalize_option_type_empty_string():
    assert normalize_option_type("") is None
    assert normalize_option_type("   ") is None

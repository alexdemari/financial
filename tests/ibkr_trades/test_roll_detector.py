"""Tests for roll_detector.py"""

import pandas as pd

from ibkr_trades.roll_detector import detect_and_tag_rolls


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_roll_detector_tags_same_day_close_open_pair():
    df = _make_df(
        [
            {
                "asset_type": "OPT",
                "underlying": "PEP",
                "option_type": "PUT",
                "expiration": "2026-07-17",
                "open_close": "C",
                "date": "2026-06-20",
                "quantity": 1.0,
            },
            {
                "asset_type": "OPT",
                "underlying": "PEP",
                "option_type": "PUT",
                "expiration": "2026-08-21",  # different expiry = roll
                "open_close": "O",
                "date": "2026-06-20",
                "quantity": -1.0,
            },
        ]
    )
    result = detect_and_tag_rolls(df)
    roll_ids = result["roll_id"].dropna().tolist()
    assert len(roll_ids) == 2
    assert roll_ids[0] == roll_ids[1]


def test_roll_detector_does_not_tag_unrelated_trades():
    df = _make_df(
        [
            {
                "asset_type": "OPT",
                "underlying": "AAPL",
                "option_type": "CALL",
                "expiration": "2026-07-17",
                "open_close": "C",
                "date": "2026-06-20",
                "quantity": 1.0,
            },
            {
                "asset_type": "OPT",
                "underlying": "PEP",
                "option_type": "PUT",
                "expiration": "2026-08-21",
                "open_close": "O",
                "date": "2026-06-20",
                "quantity": -1.0,
            },
        ]
    )
    result = detect_and_tag_rolls(df)
    assert result["roll_id"].isna().all()


def test_roll_detector_same_expiry_not_tagged_as_roll():
    df = _make_df(
        [
            {
                "asset_type": "OPT",
                "underlying": "PEP",
                "option_type": "PUT",
                "expiration": "2026-07-17",
                "open_close": "C",
                "date": "2026-06-20",
                "quantity": 1.0,
            },
            {
                "asset_type": "OPT",
                "underlying": "PEP",
                "option_type": "PUT",
                "expiration": "2026-07-17",  # same expiry = not a roll
                "open_close": "O",
                "date": "2026-06-20",
                "quantity": -1.0,
            },
        ]
    )
    result = detect_and_tag_rolls(df)
    assert result["roll_id"].isna().all()

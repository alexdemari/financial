import pandas as pd

from market_scanner.eligibility import (
    calculate_avg_volume_20,
    evaluate_symbol_eligibility,
)


def make_df(rows: int = 30, volume: int = 1_500_000) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "Open": [10.0] * rows,
            "High": [11.0] * rows,
            "Low": [9.0] * rows,
            "Close": [10.5] * rows,
            "Volume": [volume] * rows,
        }
    )


def test_calculate_avg_volume_20_uses_last_20_rows():
    df = make_df(rows=25, volume=100)
    df.loc[df.index[-20] :, "Volume"] = 200

    result = calculate_avg_volume_20(df)

    assert result == 200.0


def test_evaluate_symbol_eligibility_rejects_market_cap_first():
    result = evaluate_symbol_eligibility(
        market_cap=500_000_000,
        df=make_df(rows=220),
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        min_history_rows=200,
    )

    assert result.eligible is False
    assert result.excluded_reason == "market_cap_below_threshold"


def test_evaluate_symbol_eligibility_rejects_insufficient_history():
    result = evaluate_symbol_eligibility(
        market_cap=2_000_000_000,
        df=make_df(rows=120),
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        min_history_rows=200,
    )

    assert result.eligible is False
    assert result.excluded_reason == "insufficient_history"


def test_evaluate_symbol_eligibility_rejects_avg_volume_20():
    result = evaluate_symbol_eligibility(
        market_cap=2_000_000_000,
        df=make_df(rows=220, volume=50_000),
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        min_history_rows=200,
    )

    assert result.eligible is False
    assert result.excluded_reason == "avg_volume_20_below_threshold"


def test_evaluate_symbol_eligibility_accepts_valid_symbol():
    result = evaluate_symbol_eligibility(
        market_cap=2_000_000_000,
        df=make_df(rows=220, volume=2_000_000),
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        min_history_rows=200,
    )

    assert result.eligible is True
    assert result.excluded_reason is None
    assert result.avg_volume_20 == 2_000_000.0

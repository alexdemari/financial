import pandas as pd
import pytest

from market_scanner.trades import (
    build_trade,
    compute_trade_excursions,
    summarize_symbol_trade_records,
    summarize_trade_records,
    trade_to_record,
)


def make_window(highs: list[float], lows: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"High": highs, "Low": lows})


def test_build_trade_computes_bullish_and_bearish_directional_return():
    bullish = build_trade(
        symbol="AAPL",
        side="bullish",
        entry_date="2026-01-01T00:00:00+00:00",
        entry_price=100.0,
        exit_date="2026-01-02T00:00:00+00:00",
        exit_price=110.0,
        bars_held=2,
        entry_alignment="bullish_aligned",
        exit_reason="bars_5",
        mfe=0.12,
        mae=-0.02,
    )
    bearish = build_trade(
        symbol="MSFT",
        side="bearish",
        entry_date="2026-01-01T00:00:00+00:00",
        entry_price=100.0,
        exit_date="2026-01-02T00:00:00+00:00",
        exit_price=90.0,
        bars_held=2,
        entry_alignment="bearish_aligned",
        exit_reason="bars_5",
        mfe=0.11,
        mae=-0.03,
    )

    assert bullish.raw_return == pytest.approx(0.10)
    assert bullish.directional_return == pytest.approx(0.10)
    assert bearish.raw_return == pytest.approx(-0.10)
    assert bearish.directional_return == pytest.approx(0.10)


def test_compute_trade_excursions_for_bullish_and_bearish():
    window = make_window(highs=[101, 103, 104], lows=[99, 95, 96])

    bullish_mfe, bullish_mae = compute_trade_excursions(
        window=window,
        entry_price=100.0,
        side="bullish",
        high_column="High",
        low_column="Low",
    )
    bearish_mfe, bearish_mae = compute_trade_excursions(
        window=window,
        entry_price=100.0,
        side="bearish",
        high_column="High",
        low_column="Low",
    )

    assert bullish_mfe == pytest.approx(0.04)
    assert bullish_mae == pytest.approx(-0.05)
    assert bearish_mfe == pytest.approx(0.05)
    assert bearish_mae == pytest.approx(-0.04)


def test_summarize_trade_records_computes_expectancy():
    records = [
        trade_to_record(
            build_trade(
                symbol="AAPL",
                side="bullish",
                entry_date="2026-01-01T00:00:00+00:00",
                entry_price=100.0,
                exit_date="2026-01-03T00:00:00+00:00",
                exit_price=110.0,
                bars_held=3,
                entry_alignment="bullish_aligned",
                exit_reason="alignment_break",
                mfe=0.12,
                mae=-0.02,
            ),
            exit_rule="alignment_break",
            ranking_mode="recent-event",
        ),
        trade_to_record(
            build_trade(
                symbol="MSFT",
                side="bullish",
                entry_date="2026-01-01T00:00:00+00:00",
                entry_price=100.0,
                exit_date="2026-01-03T00:00:00+00:00",
                exit_price=95.0,
                bars_held=3,
                entry_alignment="bullish_aligned",
                exit_reason="alignment_break",
                mfe=0.03,
                mae=-0.07,
            ),
            exit_rule="alignment_break",
            ranking_mode="recent-event",
        ),
    ]

    summary = summarize_trade_records(records)
    row = summary[0]

    assert row["total_trades"] == 2
    assert row["win_rate"] == pytest.approx(0.5)
    assert row["loss_rate"] == pytest.approx(0.5)
    assert row["avg_directional_return"] == pytest.approx(0.025)
    assert row["avg_bars_held"] == pytest.approx(3.0)
    assert row["expectancy"] == pytest.approx(0.025)
    assert row["profit_factor"] == pytest.approx(2.0)


def test_summarize_trade_records_profit_factor_edge_cases():
    win_only = [
        {
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": 0.04,
            "directional_return": 0.04,
            "mfe": 0.05,
            "mae": -0.01,
            "bars_held": 5,
        }
    ]
    loss_only = [
        {
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": -0.04,
            "directional_return": -0.04,
            "mfe": 0.02,
            "mae": -0.05,
            "bars_held": 5,
        }
    ]

    assert summarize_trade_records(win_only)[0]["profit_factor"] is None
    assert summarize_trade_records(loss_only)[0]["profit_factor"] == pytest.approx(0.0)


def test_summarize_trade_records_profit_factor_zero_loss_sum():
    zero_return = [
        {
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": 0.0,
            "directional_return": 0.0,
            "mfe": 0.0,
            "mae": 0.0,
            "bars_held": 5,
        }
    ]

    assert summarize_trade_records(zero_return)[0]["profit_factor"] is None


def test_summarize_symbol_trade_records_groups_by_symbol():
    records = [
        {
            "symbol": "AAPL",
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": 0.04,
            "directional_return": 0.04,
            "mfe": 0.06,
            "mae": -0.01,
            "bars_held": 5,
        },
        {
            "symbol": "MSFT",
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": -0.02,
            "directional_return": -0.02,
            "mfe": 0.03,
            "mae": -0.04,
            "bars_held": 5,
        },
    ]

    rows = summarize_symbol_trade_records(records)

    assert {row["symbol"] for row in rows} == {"AAPL", "MSFT"}
    aapl = next(row for row in rows if row["symbol"] == "AAPL")
    assert aapl["total_trades"] == 1
    assert aapl["avg_directional_return"] == pytest.approx(0.04)

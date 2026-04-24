import pandas as pd
import pytest

from options_tech_scanner.backtest_v3 import (
    build_backtest_event,
    compute_forward_metrics,
    generate_symbol_events,
    summarize_events,
)


def make_ohlc_df(
    closes: list[float], highs: list[float], lows: list[float]
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=pd.date_range("2026-01-01", periods=len(closes), freq="D"),
    )


def make_row(**overrides) -> dict:
    row = {
        "ranking_mode": "recent-event",
        "market_state": "pullback",
        "adjusted_alignment": "bullish_aligned",
        "action_bucket": "candidate",
        "consistency_score": 2,
        "alignment": "bullish_aligned",
        "lux_signal": "BUY",
        "lux_options_hint": "CALL",
        "lux_context": "trend_confirmation_buy",
        "lux_trend": "BULLISH",
        "lux_strength": "STRONG",
        "lux_last_event": "BUY",
        "lux_days_since_last_event": 1,
        "lux_active_event": "BUY",
        "lux_days_since_active_event": 1,
        "smc_signal": "BUY",
        "smc_options_hint": "CALL",
        "smc_context": "bullish_confluence",
        "smc_bias": "BULLISH",
        "smc_range_position_pct": 45.0,
        "smc_rsi": 52.0,
    }
    row.update(overrides)
    return row


def test_compute_forward_metrics_handles_bullish_and_bearish_returns():
    df = make_ohlc_df(
        closes=[100, 101, 102, 105, 106, 108],
        highs=[101, 102, 103, 106, 107, 109],
        lows=[99, 100, 101, 104, 105, 107],
    )

    bullish = compute_forward_metrics(
        df=df,
        index=0,
        horizons=[3, 5],
        direction="bullish",
        win_threshold=0.01,
    )
    bearish = compute_forward_metrics(
        df=df,
        index=0,
        horizons=[3],
        direction="bearish",
        win_threshold=0.01,
    )

    assert bullish["return_3"] == pytest.approx(0.05)
    assert bullish["return_5"] == pytest.approx(0.08)
    assert bullish["directional_return_3"] == pytest.approx(0.05)
    assert bullish["win_3"] is True
    assert bearish["directional_return_3"] == pytest.approx(-0.05)
    assert bearish["win_3"] is False


def test_compute_forward_metrics_calculates_mfe_and_mae_by_direction():
    df = make_ohlc_df(
        closes=[100, 99, 98, 97],
        highs=[101, 103, 104, 102],
        lows=[99, 95, 94, 96],
    )

    bullish = compute_forward_metrics(
        df=df,
        index=0,
        horizons=[3],
        direction="bullish",
        win_threshold=0.01,
    )
    bearish = compute_forward_metrics(
        df=df,
        index=0,
        horizons=[3],
        direction="bearish",
        win_threshold=0.01,
    )

    assert bullish["mfe_3"] == pytest.approx(0.04)
    assert bullish["mae_3"] == pytest.approx(-0.06)
    assert bearish["mfe_3"] == pytest.approx(0.06)
    assert bearish["mae_3"] == pytest.approx(-0.04)


def test_build_backtest_event_contains_expected_schema():
    df = make_ohlc_df(
        closes=[100, 101, 102, 103],
        highs=[101, 102, 103, 104],
        lows=[99, 100, 101, 102],
    )

    event = build_backtest_event(
        symbol="AAPL",
        date=df.index[0],
        row=make_row(),
        df=df,
        index=0,
        horizons=[3],
        win_threshold=0.01,
    )

    assert event["symbol"] == "AAPL"
    assert event["ranking_mode"] == "recent-event"
    assert event["market_state"] == "pullback"
    assert event["adjusted_alignment"] == "bullish_aligned"
    assert event["action_bucket"] == "candidate"
    assert event["entry_close"] == 100.0
    assert event["return_3"] == pytest.approx(0.03)
    assert event["mfe_3"] == pytest.approx(0.04)
    assert event["win_3"] is True


def test_summarize_events_aggregates_expectancy():
    events = [
        {
            **make_row(),
            "symbol": "AAPL",
            "date": "2026-01-01T00:00:00",
            "direction": "bullish",
            "entry_close": 100.0,
            "return_3": 0.04,
            "directional_return_3": 0.04,
            "mfe_3": 0.06,
            "mae_3": -0.01,
            "win_3": True,
        },
        {
            **make_row(),
            "symbol": "MSFT",
            "date": "2026-01-02T00:00:00",
            "direction": "bullish",
            "entry_close": 100.0,
            "return_3": -0.02,
            "directional_return_3": -0.02,
            "mfe_3": 0.01,
            "mae_3": -0.03,
            "win_3": False,
        },
    ]

    summary = summarize_events(events, horizons=[3])
    row = summary[0]

    assert row["count"] == 2
    assert row["win_rate"] == 0.5
    assert row["avg_return"] == pytest.approx(0.01)
    assert row["median_return"] == pytest.approx(0.01)
    assert row["avg_mfe"] == pytest.approx(0.035)
    assert row["avg_mae"] == pytest.approx(-0.02)
    assert row["avg_win"] == pytest.approx(0.04)
    assert row["avg_loss"] == pytest.approx(0.02)
    assert row["expectancy"] == pytest.approx(0.01)


def test_generate_symbol_events_returns_no_events_for_short_series():
    df = make_ohlc_df(
        closes=[100] * 10,
        highs=[101] * 10,
        lows=[99] * 10,
    )

    events = generate_symbol_events(
        symbol="AAPL",
        df=df,
        ranking_modes=["snapshot"],
        min_bars=8,
        horizons=[3],
        win_threshold=0.01,
    )

    assert events == []


def test_generate_symbol_events_uses_only_slice_up_to_current_bar(monkeypatch):
    df = make_ohlc_df(
        closes=[100, 101, 102, 103, 104, 105],
        highs=[101, 102, 103, 104, 105, 106],
        lows=[99, 100, 101, 102, 103, 104],
    )
    observed_lengths: list[int] = []

    def fake_build_scanner_row(symbol, df_slice, *, ranking_mode, **kwargs):
        observed_lengths.append(len(df_slice))
        return make_row(ranking_mode=ranking_mode)

    monkeypatch.setattr(
        "options_tech_scanner.backtest_v3.build_scanner_row",
        fake_build_scanner_row,
    )

    events = generate_symbol_events(
        symbol="AAPL",
        df=df,
        ranking_modes=["snapshot"],
        min_bars=3,
        horizons=[2],
        win_threshold=0.01,
    )

    assert len(events) == 2
    assert observed_lengths == [3, 4]

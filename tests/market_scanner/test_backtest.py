import pandas as pd
import pytest

from market_scanner.backtest import (
    build_backtest_event,
    compute_forward_metrics,
    generate_symbol_events,
    infer_signal_side,
    prepare_backtest_df,
    render_decision_summary,
    summarize_decision_events,
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
        index=pd.date_range("2026-01-01", periods=len(closes), freq="D", tz="UTC"),
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


def test_infer_signal_side_returns_expected_labels():
    assert infer_signal_side("bullish_aligned") == "bullish"
    assert infer_signal_side("bearish_watchlist") == "bearish"
    assert infer_signal_side("mixed") == "neutral"
    assert infer_signal_side(None) == "neutral"


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
    assert bearish["return_3"] == pytest.approx(0.05)
    assert bearish["directional_return_3"] == pytest.approx(-0.05)
    assert bearish["win_3"] is False


def test_bearish_negative_raw_return_becomes_positive_directional_return():
    df = make_ohlc_df(
        closes=[100, 99, 98, 97],
        highs=[101, 100, 99, 98],
        lows=[99, 98, 97, 96],
    )

    bearish = compute_forward_metrics(
        df=df,
        index=0,
        horizons=[3],
        direction="bearish",
        win_threshold=0.01,
    )

    assert bearish["return_3"] == pytest.approx(-0.03)
    assert bearish["directional_return_3"] == pytest.approx(0.03)
    assert bearish["win_3"] is True


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
    assert event["signal_side"] == "bullish"
    assert event["action_bucket"] == "candidate"
    assert event["entry_close"] == 100.0
    assert event["return_3"] == pytest.approx(0.03)
    assert event["mfe_3"] == pytest.approx(0.04)
    assert event["win_3"] is True


def test_summarize_events_aggregates_directional_metrics_and_failure_rate():
    events = [
        {
            **make_row(),
            "symbol": "AAPL",
            "date": "2026-01-01T00:00:00+00:00",
            "signal_side": "bullish",
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
            "date": "2026-01-02T00:00:00+00:00",
            "signal_side": "bullish",
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

    assert row["signals"] == 2
    assert row["success_rate"] == 0.5
    assert row["failure_rate"] == 0.5
    assert row["avg_return"] == pytest.approx(0.01)
    assert row["avg_directional_return"] == pytest.approx(0.01)
    assert row["median_return"] == pytest.approx(0.01)
    assert row["avg_mfe"] == pytest.approx(0.035)
    assert row["avg_mae"] == pytest.approx(-0.02)
    assert row["avg_win"] == pytest.approx(0.04)
    assert row["avg_loss"] == pytest.approx(0.02)
    assert row["expectancy"] == pytest.approx(0.01)


def test_summarize_decision_events_groups_by_signal_side():
    events = [
        {
            **make_row(adjusted_alignment="bullish_aligned"),
            "symbol": "AAPL",
            "date": "2026-01-01T00:00:00+00:00",
            "signal_side": "bullish",
            "direction": "bullish",
            "entry_close": 100.0,
            "return_3": 0.04,
            "directional_return_3": 0.04,
            "mfe_3": 0.06,
            "mae_3": -0.01,
            "win_3": True,
        },
        {
            **make_row(adjusted_alignment="bearish_aligned"),
            "symbol": "MSFT",
            "date": "2026-01-02T00:00:00+00:00",
            "signal_side": "bearish",
            "direction": "bearish",
            "entry_close": 100.0,
            "return_3": -0.02,
            "directional_return_3": 0.02,
            "mfe_3": 0.03,
            "mae_3": -0.01,
            "win_3": True,
        },
    ]

    summary = summarize_decision_events(events, horizons=[3])

    assert len(summary) == 2
    assert {row["signal_side"] for row in summary} == {"bullish", "bearish"}


def test_prepare_backtest_df_applies_date_filters_and_max_bars():
    df = make_ohlc_df(
        closes=[100, 101, 102, 103, 104, 105],
        highs=[101, 102, 103, 104, 105, 106],
        lows=[99, 100, 101, 102, 103, 104],
    )

    filtered = prepare_backtest_df(
        df=df,
        start_date="2026-01-02",
        end_date="2026-01-06",
        max_bars=3,
    )

    assert list(filtered.index) == list(df.index[3:6])


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
    total_rows = 205
    df = make_ohlc_df(
        closes=[100 + index for index in range(total_rows)],
        highs=[101 + index for index in range(total_rows)],
        lows=[99 + index for index in range(total_rows)],
    )
    observed_indexes: list[int] = []

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        observed_indexes.append(index)
        assert len(lux_historical) >= index + 1
        assert len(smc_historical) >= index + 1
        return make_row(ranking_mode=ranking_mode)

    monkeypatch.setattr(
        "market_scanner.backtest.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    class FakeAnalyzer:
        def __init__(self):
            self.calls = 0

        def generate_historical_signals(self, symbol, frame):
            self.calls += 1
            return pd.DataFrame(
                {
                    "date": frame.index,
                    "close": frame["Close"].to_numpy(),
                    "trend": ["BULLISH"] * len(frame),
                    "strength": ["STRONG"] * len(frame),
                    "adx": [25.0] * len(frame),
                    "confirmation_signal": [1] * len(frame),
                    "contrarian_signal": [0] * len(frame),
                    "combined_signal": [1] * len(frame),
                    "options_hint": ["CALL"] * len(frame),
                    "signal_context": ["trend_confirmation_buy"] * len(frame),
                    "signal_bias": ["BULLISH"] * len(frame),
                    "range_position_pct": [45.0] * len(frame),
                    "rsi": [52.0] * len(frame),
                    "long_signal": [True] * len(frame),
                    "short_signal": [False] * len(frame),
                    "swing_high_marker": [False] * len(frame),
                    "swing_low_marker": [False] * len(frame),
                    "in_premium": [False] * len(frame),
                    "in_discount": [True] * len(frame),
                    "bullish_rejection": [False] * len(frame),
                    "bearish_rejection": [False] * len(frame),
                }
            )

    lux_analyzer = FakeAnalyzer()
    smc_analyzer = FakeAnalyzer()

    events = generate_symbol_events(
        symbol="AAPL",
        df=df,
        ranking_modes=["snapshot"],
        min_bars=120,
        horizons=[2],
        win_threshold=0.01,
        lux_analyzer=lux_analyzer,
        smc_analyzer=smc_analyzer,
    )

    assert len(events) == 4
    assert observed_indexes == [199, 200, 201, 202]
    assert lux_analyzer.calls == 1
    assert smc_analyzer.calls == 1


def test_generate_symbol_events_respects_scanner_history_floor(monkeypatch):
    total_rows = 205
    df = make_ohlc_df(
        closes=[100 + index for index in range(total_rows)],
        highs=[101 + index for index in range(total_rows)],
        lows=[99 + index for index in range(total_rows)],
    )
    observed_indexes: list[int] = []

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        observed_indexes.append(index)
        return make_row(ranking_mode=ranking_mode)

    monkeypatch.setattr(
        "market_scanner.backtest.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    class FakeAnalyzer:
        def generate_historical_signals(self, symbol, frame):
            return pd.DataFrame(
                {
                    "date": frame.index,
                    "close": frame["Close"].to_numpy(),
                    "trend": ["BULLISH"] * len(frame),
                    "strength": ["STRONG"] * len(frame),
                    "adx": [25.0] * len(frame),
                    "confirmation_signal": [1] * len(frame),
                    "contrarian_signal": [0] * len(frame),
                    "combined_signal": [1] * len(frame),
                    "options_hint": ["CALL"] * len(frame),
                    "signal_context": ["trend_confirmation_buy"] * len(frame),
                    "signal_bias": ["BULLISH"] * len(frame),
                    "range_position_pct": [45.0] * len(frame),
                    "rsi": [52.0] * len(frame),
                    "long_signal": [True] * len(frame),
                    "short_signal": [False] * len(frame),
                    "swing_high_marker": [False] * len(frame),
                    "swing_low_marker": [False] * len(frame),
                    "in_premium": [False] * len(frame),
                    "in_discount": [True] * len(frame),
                    "bullish_rejection": [False] * len(frame),
                    "bearish_rejection": [False] * len(frame),
                }
            )

    events = generate_symbol_events(
        symbol="AAPL",
        df=df,
        ranking_modes=["recent-event"],
        min_bars=120,
        horizons=[3],
        win_threshold=0.01,
        lux_analyzer=FakeAnalyzer(),
        smc_analyzer=FakeAnalyzer(),
    )

    assert len(events) == 3
    assert observed_indexes == [199, 200, 201]


def test_render_decision_summary_uses_directional_metrics_not_avg_return():
    summary_df = pd.DataFrame(
        [
            {
                "signal_side": "bearish",
                "action_bucket": "candidate",
                "market_state": "pullback",
                "lux_strength": "STRONG",
                "ranking_mode": "recent-event",
                "horizon": 10,
                "signals": 53,
                "success_rate": 0.585,
                "failure_rate": 0.415,
                "avg_directional_return": 0.021,
                "avg_return": -0.018,
                "expectancy": 0.008,
            },
            {
                "signal_side": "neutral",
                "action_bucket": "watchlist",
                "market_state": "range",
                "lux_strength": "NORMAL",
                "ranking_mode": "recent-event",
                "horizon": 10,
                "signals": 20,
                "success_rate": None,
                "failure_rate": None,
                "avg_directional_return": None,
                "avg_return": 0.0,
                "expectancy": None,
            },
        ]
    )

    rendered = render_decision_summary(summary_df)

    assert "BEARISH signal | candidate | pullback | STRONG | h=10" in rendered
    assert "signals=53 | success=58.5% | failure=41.5%" in rendered
    assert "avg_directional_return=+2.1%" in rendered
    assert "avg_return" not in rendered
    assert "neutral" not in rendered.lower()

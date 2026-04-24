from types import SimpleNamespace

import pandas as pd

from options_tech_scanner.scan import _smc_context, scan_universe
from options_tech_scanner.report_writer import render_top_n_summary
from stock_analyzer.signals.smc import SMCSignalGenerator


def make_csv(path, rows: int = 220, volume: int = 2_000_000):
    pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "Open": [10.0] * rows,
            "High": [11.0] * rows,
            "Low": [9.0] * rows,
            "Close": [10.5] * rows,
            "Volume": [volume] * rows,
        }
    ).to_csv(path, index=False)


def test_scan_universe_generates_csv_and_sorts_top_results(
    tmp_path, monkeypatch, capsys
):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "MISSING"],
            "market_cap": [2_000_000_000, 3_000_000_000, 4_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_csv(data_dir / "AAPL.csv")
    make_csv(data_dir / "MSFT.csv")

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.signal_model = signal_model

        def generate_signal(self, symbol, df):
            if self.signal_model == "lux":
                if symbol == "AAPL":
                    return SimpleNamespace(
                        close_price=10.5,
                        combined_signal=1,
                        options_hint="CALL",
                        trend="BULLISH",
                        strength="STRONG",
                        adx=28.0,
                        confirmation_signal=1,
                        contrarian_signal=0,
                    )
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=-1,
                    options_hint="PUT",
                    trend="BEARISH",
                    strength="NORMAL",
                    adx=18.0,
                    confirmation_signal=-1,
                    contrarian_signal=0,
                )

            if symbol == "AAPL":
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=1,
                    options_hint="CALL",
                    long_signal=True,
                    short_signal=False,
                    swing_low_marker=False,
                    swing_high_marker=False,
                    in_discount=True,
                    in_premium=False,
                    bullish_rejection=False,
                    bearish_rejection=False,
                    bias="BULLISH",
                    range_position_pct=22.0,
                    rsi=45.0,
                )
            return SimpleNamespace(
                close_price=10.5,
                combined_signal=0,
                options_hint="NO_TRADE",
                long_signal=False,
                short_signal=False,
                swing_low_marker=False,
                swing_high_marker=False,
                in_discount=False,
                in_premium=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
            )

        def generate_historical_signals(self, symbol, df):
            if self.signal_model == "lux":
                if symbol == "AAPL":
                    return pd.DataFrame(
                        {
                            "date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
                            "combined_signal": [0, 1],
                            "signal_context": ["no_trade", "trend_confirmation_buy"],
                            "options_hint": ["NO_TRADE", "CALL"],
                        }
                    )
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
                        "combined_signal": [0, -1],
                        "signal_context": ["no_trade", "trend_confirmation_sell"],
                        "options_hint": ["NO_TRADE", "PUT"],
                    }
                )

            if symbol == "AAPL":
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
                        "combined_signal": [0, 1],
                        "signal_context": ["swing_low_watch", "bullish_confluence"],
                        "options_hint": ["CALL_WATCH", "CALL"],
                    }
                )
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-08-06", "2026-08-07"]),
                    "combined_signal": [0, 0],
                    "signal_context": ["premium_watch", "no_trade"],
                    "options_hint": ["PUT_WATCH", "NO_TRADE"],
                }
            )

    monkeypatch.setattr("options_tech_scanner.scan.StockDataAnalyzer", FakeAnalyzer)

    output_file = tmp_path / "scan.csv"
    result_df, written_path = scan_universe(
        universe_file=universe_file,
        data_dir=data_dir,
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        top=10,
        output=output_file,
    )

    eligible = result_df[result_df["eligible"]]
    assert written_path == output_file
    assert output_file.exists()
    assert eligible.iloc[0]["symbol"] == "AAPL"
    assert eligible.iloc[0]["consistency_score"] == 4
    assert eligible.iloc[0]["alignment"] == "bullish_aligned"
    assert eligible.iloc[0]["market_state"] == "unknown"
    assert eligible.iloc[0]["adjusted_alignment"] == "bullish_aligned"
    assert eligible.iloc[0]["action_bucket"] == "needs_review"
    assert eligible.iloc[0]["lux_last_event"] == "BUY"
    assert eligible.iloc[0]["smc_last_event_options_hint"] == "CALL"
    assert (
        result_df.loc[result_df["symbol"] == "MISSING", "excluded_reason"].item()
        == "missing_csv"
    )
    assert (
        result_df.loc[result_df["symbol"] == "MISSING", "market_state"].item()
        == "unknown"
    )
    assert (
        result_df.loc[result_df["symbol"] == "MISSING", "adjusted_alignment"].item()
        == "no_trade"
    )
    assert (
        result_df.loc[result_df["symbol"] == "MISSING", "action_bucket"].item()
        == "avoid"
    )

    stdout = capsys.readouterr().out
    assert "AAPL" in stdout
    assert "MSFT" in stdout
    assert "adjusted_alignment" in stdout
    assert "market_state" in stdout
    assert "action_bucket" in stdout
    assert "Exported:" in stdout


def test_scan_universe_recent_event_mode_uses_watch_events_for_ranking(
    tmp_path, monkeypatch, capsys
):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["NVTS", "HOOD"],
            "market_cap": [2_000_000_000, 3_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_csv(data_dir / "NVTS.csv")
    make_csv(data_dir / "HOOD.csv")

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.signal_model = signal_model

        def generate_signal(self, symbol, df):
            if self.signal_model == "lux":
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=0,
                    options_hint="NO_TRADE",
                    trend="BULLISH",
                    strength="NORMAL",
                    adx=21.0,
                    confirmation_signal=0,
                    contrarian_signal=0,
                )

            return SimpleNamespace(
                close_price=10.5,
                combined_signal=0,
                options_hint="NO_TRADE",
                long_signal=False,
                short_signal=False,
                swing_low_marker=False,
                swing_high_marker=False,
                in_discount=False,
                in_premium=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
            )

        def generate_historical_signals(self, symbol, df):
            if self.signal_model == "lux":
                if symbol == "NVTS":
                    return pd.DataFrame(
                        {
                            "date": pd.to_datetime(
                                ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
                            ),
                            "combined_signal": [0, 1, -1, -1],
                            "signal_context": [
                                "no_trade",
                                "trend_confirmation_buy",
                                "contrarian_reversal_sell",
                                "contrarian_reversal_sell",
                            ],
                            "options_hint": ["NO_TRADE", "CALL", "PUT", "PUT"],
                        }
                    )
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(
                            ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
                        ),
                        "combined_signal": [0, -1, 0, 0],
                        "signal_context": [
                            "no_trade",
                            "trend_confirmation_sell",
                            "no_trade",
                            "no_trade",
                        ],
                        "options_hint": ["NO_TRADE", "PUT", "NO_TRADE", "NO_TRADE"],
                    }
                )

            if symbol == "NVTS":
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(
                            ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
                        ),
                        "combined_signal": [0, 0, 0, 0],
                        "signal_context": [
                            "no_trade",
                            "short_term_bullish_reversal",
                            "premium_watch",
                            "no_trade",
                        ],
                        "options_hint": [
                            "NO_TRADE",
                            "CALL_WATCH",
                            "PUT_WATCH",
                            "NO_TRADE",
                        ],
                    }
                )
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(
                        ["2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
                    ),
                    "combined_signal": [0, 0, 0, 0],
                    "signal_context": [
                        "no_trade",
                        "short_term_bearish_reversal",
                        "discount_watch",
                        "no_trade",
                    ],
                    "options_hint": [
                        "NO_TRADE",
                        "PUT_WATCH",
                        "CALL_WATCH",
                        "NO_TRADE",
                    ],
                }
            )

    monkeypatch.setattr("options_tech_scanner.scan.StockDataAnalyzer", FakeAnalyzer)

    output_file = tmp_path / "scan_recent_event.csv"
    result_df, _ = scan_universe(
        universe_file=universe_file,
        data_dir=data_dir,
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        top=10,
        output=output_file,
        ranking_mode="recent-event",
    )

    nvts = result_df.loc[result_df["symbol"] == "NVTS"].iloc[0]
    hood = result_df.loc[result_df["symbol"] == "HOOD"].iloc[0]

    assert nvts["ranking_mode"] == "recent-event"
    assert nvts["lux_options_hint"] == "NO_TRADE"
    assert nvts["lux_last_event_options_hint"] == "PUT"
    assert nvts["lux_active_event_options_hint"] == "CALL"
    assert nvts["lux_active_event"] == "BUY"
    assert nvts["smc_last_event_options_hint"] == "PUT_WATCH"
    assert nvts["smc_active_event_options_hint"] == "CALL_WATCH"
    assert nvts["smc_active_event"] == "HOLD"
    assert nvts["smc_days_since_active_event"] == 2
    assert nvts["market_state"] == "early_trend"
    assert nvts["adjusted_alignment"] == "bullish_aligned"
    assert nvts["action_bucket"] == "candidate"
    assert nvts["alignment"] == "bullish_aligned"
    assert nvts["consistency_score"] == 1
    assert hood["alignment"] == "bearish_aligned"
    assert hood["market_state"] == "early_trend"
    assert hood["adjusted_alignment"] == "bearish_aligned"
    assert hood["action_bucket"] == "candidate"
    assert hood["consistency_score"] == 1

    stdout = capsys.readouterr().out
    assert "lux_trend" in stdout
    assert "adjusted_alignment" in stdout
    assert "market_state" in stdout


def test_smc_active_event_prefers_latest_reversal_over_older_confluence(
    tmp_path, monkeypatch
):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "market_cap": [2_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_csv(data_dir / "AAPL.csv")

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.signal_model = signal_model

        def generate_signal(self, symbol, df):
            if self.signal_model == "lux":
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=0,
                    options_hint="NO_TRADE",
                    trend="BULLISH",
                    strength="NORMAL",
                    adx=20.0,
                    confirmation_signal=0,
                    contrarian_signal=0,
                )

            return SimpleNamespace(
                close_price=10.5,
                combined_signal=0,
                options_hint="NO_TRADE",
                long_signal=False,
                short_signal=False,
                swing_low_marker=False,
                swing_high_marker=False,
                in_discount=False,
                in_premium=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
            )

        def generate_historical_signals(self, symbol, df):
            if self.signal_model == "lux":
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(["2026-03-06", "2026-03-30"]),
                        "combined_signal": [0, 0],
                        "signal_context": ["no_trade", "no_trade"],
                        "options_hint": ["NO_TRADE", "NO_TRADE"],
                    }
                )

            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-03-06", "2026-03-30", "2026-04-21"]),
                    "combined_signal": [1, 0, 0],
                    "signal_context": [
                        "bullish_confluence",
                        "short_term_bullish_reversal",
                        "no_trade",
                    ],
                    "options_hint": ["CALL", "CALL_WATCH", "NO_TRADE"],
                }
            )

    monkeypatch.setattr("options_tech_scanner.scan.StockDataAnalyzer", FakeAnalyzer)

    result_df, _ = scan_universe(
        universe_file=universe_file,
        data_dir=data_dir,
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        top=10,
        output=tmp_path / "scan.csv",
        ranking_mode="recent-event",
    )

    aapl = result_df.loc[result_df["symbol"] == "AAPL"].iloc[0]

    assert aapl["smc_last_event_options_hint"] == "CALL_WATCH"
    assert aapl["smc_last_event_context"] == "short_term_bullish_reversal"
    assert aapl["smc_active_event_options_hint"] == "CALL_WATCH"
    assert aapl["smc_active_event_context"] == "short_term_bullish_reversal"
    assert aapl["smc_days_since_active_event"] == 22
    assert aapl["market_state"] == "unknown"
    assert aapl["adjusted_alignment"] == "mixed"
    assert aapl["action_bucket"] == "needs_review"


def test_smc_context_matches_historical_adapter_context():
    cases = [
        {
            "long_signal": True,
            "short_signal": False,
            "swing_low_marker": False,
            "swing_high_marker": False,
            "in_discount": False,
            "in_premium": False,
            "bullish_rejection": False,
            "bearish_rejection": False,
        },
        {
            "long_signal": False,
            "short_signal": False,
            "swing_low_marker": True,
            "swing_high_marker": False,
            "in_discount": True,
            "in_premium": False,
            "bullish_rejection": False,
            "bearish_rejection": False,
        },
        {
            "long_signal": False,
            "short_signal": False,
            "swing_low_marker": False,
            "swing_high_marker": False,
            "in_discount": True,
            "in_premium": False,
            "bullish_rejection": True,
            "bearish_rejection": False,
        },
        {
            "long_signal": False,
            "short_signal": False,
            "swing_low_marker": False,
            "swing_high_marker": True,
            "in_discount": False,
            "in_premium": False,
            "bullish_rejection": False,
            "bearish_rejection": False,
        },
    ]

    for case in cases:
        signal = SimpleNamespace(**case)
        historical_row = pd.Series(case)
        assert _smc_context(signal) == SMCSignalGenerator._signal_context(
            historical_row
        )


def test_recent_event_mode_falls_back_to_no_trade_without_active_directional_event(
    tmp_path, monkeypatch
):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "market_cap": [2_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_csv(data_dir / "AAPL.csv")

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.signal_model = signal_model

        def generate_signal(self, symbol, df):
            if self.signal_model == "lux":
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=0,
                    options_hint="NO_TRADE",
                    trend="BULLISH",
                    strength="NORMAL",
                    adx=20.0,
                    confirmation_signal=0,
                    contrarian_signal=0,
                )

            return SimpleNamespace(
                close_price=10.5,
                combined_signal=0,
                options_hint="NO_TRADE",
                long_signal=False,
                short_signal=False,
                swing_low_marker=False,
                swing_high_marker=False,
                in_discount=False,
                in_premium=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
            )

        def generate_historical_signals(self, symbol, df):
            if self.signal_model == "lux":
                return pd.DataFrame(
                    {
                        "date": pd.to_datetime(["2026-04-21", "2026-04-22"]),
                        "combined_signal": [0, 0],
                        "signal_context": ["no_trade", "no_trade"],
                        "options_hint": ["NO_TRADE", "NO_TRADE"],
                    }
                )

            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2026-04-21", "2026-04-22"]),
                    "combined_signal": [0, 0],
                    "signal_context": ["premium_watch", "no_trade"],
                    "options_hint": ["PUT_WATCH", "NO_TRADE"],
                }
            )

    monkeypatch.setattr("options_tech_scanner.scan.StockDataAnalyzer", FakeAnalyzer)

    result_df, _ = scan_universe(
        universe_file=universe_file,
        data_dir=data_dir,
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        top=10,
        output=tmp_path / "scan_recent_event.csv",
        ranking_mode="recent-event",
    )

    aapl = result_df.loc[result_df["symbol"] == "AAPL"].iloc[0]

    assert aapl["lux_last_event"] is None
    assert aapl["lux_active_event"] is None
    assert aapl["smc_last_event_options_hint"] == "PUT_WATCH"
    assert aapl["smc_active_event"] is None
    assert aapl["smc_active_event_options_hint"] is None
    assert aapl["market_state"] == "unknown"
    assert aapl["adjusted_alignment"] == "no_trade"
    assert aapl["action_bucket"] == "avoid"
    assert aapl["alignment"] == "no_trade"
    assert aapl["consistency_score"] == 0


def test_render_top_n_summary_uses_v2_decision_columns():
    summary_df = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "close": 10.5,
                "lux_trend": "BULLISH",
                "lux_strength": "STRONG",
                "smc_range_position_pct": 55.0,
                "smc_rsi": 52.0,
                "alignment": "bullish_aligned",
                "adjusted_alignment": "bullish_aligned",
                "market_state": "early_trend",
                "action_bucket": "candidate",
                "consistency_score": 4,
            }
        ]
    )

    summary = render_top_n_summary(summary_df, top=10)

    assert "lux_trend" in summary
    assert "lux_strength" in summary
    assert "smc_range_position_pct" in summary
    assert "smc_rsi" in summary
    assert "adjusted_alignment" in summary
    assert "market_state" in summary
    assert "action_bucket" in summary

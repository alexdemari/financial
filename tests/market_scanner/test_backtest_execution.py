from types import SimpleNamespace

import pandas as pd

from market_scanner.backtest_execution import (
    backtest_execution_universe,
    generate_symbol_trades,
    rank_execution_rules,
    render_execution_rule_comparison,
    resolve_exit_rules,
    summarize_execution_rules,
)
from market_scanner.pipeline import SymbolData


def make_ohlc_df(rows: int = 205) -> pd.DataFrame:
    closes = [100.0 + index for index in range(rows)]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1.0 for value in closes],
            "Low": [value - 1.0 for value in closes],
            "Close": closes,
            "Volume": [1_000_000] * rows,
        },
        index=pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC"),
    )


def make_row(**overrides) -> dict:
    row = {
        "ranking_mode": "recent-event",
        "market_state": "pullback",
        "adjusted_alignment": "bullish_aligned",
        "action_bucket": "candidate",
    }
    row.update(overrides)
    return row


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


def test_generate_symbol_trades_opens_bullish_and_closes_on_bucket_downgrade(
    monkeypatch,
):
    df = make_ohlc_df()
    rows = {
        199: make_row(
            adjusted_alignment="bullish_aligned",
            action_bucket="candidate",
            market_state="pullback",
        ),
        200: make_row(
            adjusted_alignment="bullish_watchlist",
            action_bucket="watchlist",
            market_state="range",
        ),
    }

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        return rows.get(
            index, make_row(action_bucket="avoid", adjusted_alignment="no_trade")
        )

    monkeypatch.setattr(
        "market_scanner.backtest_execution.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    trades = generate_symbol_trades(
        symbol="AAPL",
        df=df,
        ranking_mode="recent-event",
        exit_rule="bucket_downgrade",
        min_bars=120,
        lux_analyzer=FakeAnalyzer(),
        smc_analyzer=FakeAnalyzer(),
    )

    assert len(trades) == 1
    trade = trades[0]
    assert trade.side == "bullish"
    assert trade.entry_alignment == "bullish_aligned"
    assert trade.exit_reason == "bucket_downgrade"
    assert trade.bars_held == 2


def test_generate_symbol_trades_does_not_open_on_watchlist_or_no_trade(monkeypatch):
    df = make_ohlc_df()
    rows = {
        199: make_row(
            adjusted_alignment="bullish_watchlist",
            action_bucket="watchlist",
            market_state="range",
        ),
        200: make_row(
            adjusted_alignment="no_trade",
            action_bucket="avoid",
            market_state="unknown",
        ),
        201: make_row(
            adjusted_alignment="bullish_aligned",
            action_bucket="candidate",
            market_state="pullback",
        ),
    }

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        return rows.get(
            index, make_row(action_bucket="avoid", adjusted_alignment="no_trade")
        )

    monkeypatch.setattr(
        "market_scanner.backtest_execution.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    trades = generate_symbol_trades(
        symbol="AAPL",
        df=df,
        ranking_mode="recent-event",
        exit_rule="bars_5",
        min_bars=120,
        lux_analyzer=FakeAnalyzer(),
        smc_analyzer=FakeAnalyzer(),
    )

    assert len(trades) == 1
    assert trades[0].entry_date == pd.Timestamp(df.index[201]).isoformat()
    assert trades[0].exit_reason == "end_of_data"


def test_generate_symbol_trades_exits_before_same_bar_reentry(monkeypatch):
    df = make_ohlc_df()
    rows = {
        199: make_row(
            adjusted_alignment="bullish_aligned",
            action_bucket="candidate",
        ),
        200: make_row(
            adjusted_alignment="bearish_aligned",
            action_bucket="candidate",
        ),
        201: make_row(
            adjusted_alignment="bearish_aligned",
            action_bucket="candidate",
        ),
        202: make_row(
            adjusted_alignment="bullish_watchlist",
            action_bucket="watchlist",
        ),
    }

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        return rows.get(
            index, make_row(action_bucket="avoid", adjusted_alignment="no_trade")
        )

    monkeypatch.setattr(
        "market_scanner.backtest_execution.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    trades = generate_symbol_trades(
        symbol="AAPL",
        df=df,
        ranking_mode="recent-event",
        exit_rule="alignment_break",
        min_bars=120,
        lux_analyzer=FakeAnalyzer(),
        smc_analyzer=FakeAnalyzer(),
    )

    assert len(trades) == 2
    assert trades[0].side == "bullish"
    assert trades[0].exit_date == pd.Timestamp(df.index[200]).isoformat()
    assert trades[1].side == "bearish"
    assert trades[1].entry_date == pd.Timestamp(df.index[201]).isoformat()


def test_generate_symbol_trades_force_closes_at_end_of_data(monkeypatch):
    df = make_ohlc_df()

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        if index == 199:
            return make_row(
                adjusted_alignment="bearish_aligned",
                action_bucket="candidate",
            )
        return make_row(
            adjusted_alignment="bearish_aligned",
            action_bucket="candidate",
        )

    monkeypatch.setattr(
        "market_scanner.backtest_execution.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    trades = generate_symbol_trades(
        symbol="MSFT",
        df=df,
        ranking_mode="recent-event",
        exit_rule="opposite_signal",
        min_bars=120,
        lux_analyzer=FakeAnalyzer(),
        smc_analyzer=FakeAnalyzer(),
    )

    assert len(trades) == 1
    assert trades[0].side == "bearish"
    assert trades[0].exit_reason == "end_of_data"
    assert trades[0].exit_date == pd.Timestamp(df.index[-1]).isoformat()


def test_backtest_execution_universe_exports_required_schema(tmp_path, monkeypatch):
    df = make_ohlc_df()

    monkeypatch.setattr(
        "market_scanner.backtest_execution.load_selected_universe",
        lambda universe_file, symbols=None: pd.DataFrame(
            {"symbol": ["AAPL"], "market_cap": [2_000_000_000]}
        ),
    )
    monkeypatch.setattr(
        "market_scanner.backtest_execution.create_analyzers",
        lambda analyzer_cls: SimpleNamespace(
            lux_analyzer=FakeAnalyzer(),
            smc_analyzer=FakeAnalyzer(),
        ),
    )
    monkeypatch.setattr(
        "market_scanner.backtest_execution.iter_symbol_data",
        lambda universe, data_dir, transform_df=None: [
            SymbolData(
                symbol="AAPL",
                market_cap=2_000_000_000,
                df=transform_df(df) if transform_df else df,
                load_error=None,
            )
        ],
    )

    def fake_build_scanner_row_from_history(
        symbol, *, close, lux_historical, smc_historical, index, ranking_mode, **kwargs
    ):
        if index == 199:
            return make_row(
                adjusted_alignment="bullish_aligned",
                action_bucket="candidate",
            )
        return make_row(
            adjusted_alignment="bullish_watchlist",
            action_bucket="watchlist",
            market_state="range",
        )

    monkeypatch.setattr(
        "market_scanner.backtest_execution.build_scanner_row_from_history",
        fake_build_scanner_row_from_history,
    )

    trades_df, summary_df = backtest_execution_universe(
        universe_file=tmp_path / "universe.csv",
        data_dir=tmp_path / "data",
        ranking_mode="recent-event",
        exit_rule="bucket_downgrade",
        output_trades=tmp_path / "execution_trades.csv",
        output_summary=tmp_path / "execution_summary.csv",
        output_comparison=tmp_path / "execution_rule_comparison.csv",
    )

    assert set(
        [
            "symbol",
            "side",
            "entry_date",
            "entry_price",
            "exit_date",
            "exit_price",
            "bars_held",
            "entry_alignment",
            "exit_reason",
            "raw_return",
            "directional_return",
            "mfe",
            "mae",
            "exit_rule",
            "ranking_mode",
        ]
    ).issubset(trades_df.columns)
    assert set(
        [
            "exit_rule",
            "ranking_mode",
            "side",
            "entry_alignment",
            "total_trades",
            "win_rate",
            "loss_rate",
            "avg_return",
            "median_return",
            "avg_directional_return",
            "median_directional_return",
            "avg_mfe",
            "avg_mae",
            "avg_bars_held",
            "expectancy",
            "profit_factor",
            "best_trade",
            "worst_trade",
        ]
    ).issubset(summary_df.columns)
    comparison_df = pd.read_csv(tmp_path / "execution_rule_comparison.csv")
    assert set(
        [
            "rank",
            "qualified",
            "qualification_reason",
            "exit_rule",
            "ranking_mode",
            "side",
            "entry_alignment",
            "total_trades",
            "win_rate",
            "loss_rate",
            "avg_directional_return",
            "median_directional_return",
            "expectancy",
            "profit_factor",
            "avg_mfe",
            "avg_mae",
            "avg_bars_held",
            "best_trade",
            "worst_trade",
        ]
    ).issubset(comparison_df.columns)


def test_resolve_exit_rules_expands_all():
    assert resolve_exit_rules("all") == [
        "alignment_break",
        "bucket_downgrade",
        "late_state",
        "opposite_signal",
        "bars_5",
        "bars_10",
        "bars_20",
    ]
    assert resolve_exit_rules("bars_10") == ["bars_10"]


def test_summarize_execution_rules_groups_all_rules():
    records = [
        {
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "raw_return": 0.05,
            "directional_return": 0.05,
            "mfe": 0.08,
            "mae": -0.01,
            "bars_held": 5,
        },
        {
            "exit_rule": "bars_10",
            "ranking_mode": "recent-event",
            "side": "bearish",
            "entry_alignment": "bearish_aligned",
            "raw_return": -0.04,
            "directional_return": 0.04,
            "mfe": 0.06,
            "mae": -0.02,
            "bars_held": 10,
        },
    ]

    rows = summarize_execution_rules(records, min_trades=1)

    groups = {
        (
            row["exit_rule"],
            row["ranking_mode"],
            row["side"],
            row["entry_alignment"],
        )
        for row in rows
    }
    assert groups == {
        ("bars_5", "recent-event", "bullish", "bullish_aligned"),
        ("bars_10", "recent-event", "bearish", "bearish_aligned"),
    }


def test_rank_execution_rules_qualification_and_order():
    rows = [
        {
            "exit_rule": "bars_5",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "total_trades": 30,
            "win_rate": 0.7,
            "loss_rate": 0.3,
            "avg_directional_return": 0.03,
            "median_directional_return": 0.02,
            "expectancy": 0.02,
            "profit_factor": 1.2,
            "avg_mfe": 0.05,
            "avg_mae": -0.03,
            "avg_bars_held": 5.0,
            "best_trade": 0.08,
            "worst_trade": -0.02,
        },
        {
            "exit_rule": "bars_10",
            "ranking_mode": "recent-event",
            "side": "bullish",
            "entry_alignment": "bullish_aligned",
            "total_trades": 30,
            "win_rate": 0.7,
            "loss_rate": 0.3,
            "avg_directional_return": 0.04,
            "median_directional_return": 0.03,
            "expectancy": 0.03,
            "profit_factor": 1.1,
            "avg_mfe": 0.06,
            "avg_mae": -0.02,
            "avg_bars_held": 10.0,
            "best_trade": 0.09,
            "worst_trade": -0.02,
        },
        {
            "exit_rule": "late_state",
            "ranking_mode": "recent-event",
            "side": "bearish",
            "entry_alignment": "bearish_aligned",
            "total_trades": 7,
            "win_rate": 0.4,
            "loss_rate": 0.6,
            "avg_directional_return": -0.01,
            "median_directional_return": -0.01,
            "expectancy": -0.01,
            "profit_factor": 0.8,
            "avg_mfe": 0.02,
            "avg_mae": -0.05,
            "avg_bars_held": 4.0,
            "best_trade": 0.03,
            "worst_trade": -0.06,
        },
    ]

    ranked = rank_execution_rules(rows, min_trades=20)

    assert ranked[0]["exit_rule"] == "bars_10"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["qualification_reason"] == "qualified"
    assert ranked[-1]["qualified"] is False
    assert ranked[-1]["qualification_reason"] == (
        "not enough trades; negative expectancy; " "negative avg directional return"
    )


def test_render_execution_rule_comparison_shows_required_sections():
    comparison_df = pd.DataFrame(
        rank_execution_rules(
            [
                {
                    "exit_rule": "bucket_downgrade",
                    "ranking_mode": "recent-event",
                    "side": "bullish",
                    "entry_alignment": "bullish_aligned",
                    "total_trades": 21,
                    "win_rate": 0.6,
                    "loss_rate": 0.4,
                    "avg_directional_return": 0.03,
                    "median_directional_return": 0.02,
                    "expectancy": 0.02,
                    "profit_factor": 1.5,
                    "avg_mfe": 0.06,
                    "avg_mae": -0.02,
                    "avg_bars_held": 8.0,
                    "best_trade": 0.1,
                    "worst_trade": -0.03,
                },
                {
                    "exit_rule": "opposite_signal",
                    "ranking_mode": "recent-event",
                    "side": "bearish",
                    "entry_alignment": "bearish_aligned",
                    "total_trades": 3,
                    "win_rate": 0.3,
                    "loss_rate": 0.7,
                    "avg_directional_return": -0.01,
                    "median_directional_return": -0.01,
                    "expectancy": -0.01,
                    "profit_factor": 0.5,
                    "avg_mfe": 0.02,
                    "avg_mae": -0.04,
                    "avg_bars_held": 6.0,
                    "best_trade": 0.02,
                    "worst_trade": -0.05,
                },
            ],
            min_trades=20,
        )
    )

    output = render_execution_rule_comparison(comparison_df)

    assert "BEST EXECUTION RULES" in output
    assert "UNQUALIFIED RULES" in output
    assert "expectancy" in output
    assert "avg_dir_return" in output
    assert "profit_factor" in output

from datetime import date

import pandas as pd

from dividend_tracker.backtest import (
    AssetBacktestResult,
    ModelResult,
    _evaluate_model,
    write_report,
)
from stock_analyzer.enums import Signal


def test_evaluate_model_filters_requested_period_and_tracks_drawdown(monkeypatch):
    class FakeAnalyzer:
        def __init__(self, signal_model):
            self.signal_model = signal_model

        def generate_historical_signals(self, symbol, ohlc_df):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2021-12-15", "2022-01-10"]),
                    "combined_signal": [Signal.BUY, Signal.BUY],
                }
            )

    dates = pd.date_range("2022-01-01", periods=90, freq="D")
    ohlc_df = pd.DataFrame(
        {
            "Open": 100.0,
            "High": 110.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 1_000_000.0,
        },
        index=dates,
    )
    ohlc_df.loc[pd.Timestamp("2022-01-20"), "Low"] = 90.0
    ohlc_df.loc[pd.Timestamp("2022-02-24"), "Close"] = 106.0
    monkeypatch.setattr("dividend_tracker.backtest.StockDataAnalyzer", FakeAnalyzer)

    result = _evaluate_model(
        "lux",
        "TEST",
        ohlc_df,
        start_date="2022-01-01",
        end_date="2022-05-31",
    )

    assert result.total_signals == 1
    assert result.precision == 1.0
    assert result.false_positive == 0.0
    assert result.max_drawdown == -0.10
    assert result.period_start == date(2022, 1, 1)


def test_write_report_includes_required_sections(tmp_path):
    output_path = tmp_path / "comparison.md"
    results = [
        AssetBacktestResult(
            config_ticker="EGIE3",
            ticker="EGIE3.SA",
            current_model="smc",
            recommended_model="smc",
            changed=False,
            change_reason="Current model is best",
            models={
                "smc": ModelResult(
                    model="smc",
                    total_signals=8,
                    precision=0.375,
                    false_positive=0.125,
                    neutral=0.5,
                    max_drawdown=-0.08,
                    period_start=date(2022, 1, 3),
                    period_end=date(2026, 5, 29),
                )
            },
        )
    ]

    write_report(
        results,
        output_path=output_path,
        run_date=date(2026, 6, 10),
        yaml_updated=[],
        start_date="2022-01-01",
        end_date="2026-05-31",
    )

    report = output_path.read_text(encoding="utf-8")
    assert "# Backtest" in report
    assert "## Metodologia" in report
    assert "## Resumo consolidado" in report
    assert "## Decisões" in report
    assert "| EGIE3.SA | smc | smc | 37.5% | 37.5% | Não |" in report

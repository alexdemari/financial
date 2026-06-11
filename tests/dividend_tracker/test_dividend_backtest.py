from datetime import date

import pandas as pd
import pytest

from dividend_tracker.backtest import (
    AssetBacktestResult,
    ModelResult,
    _evaluate_model,
    calculate_combined_signals,
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


def test_evaluate_model_computes_extended_metrics(monkeypatch):
    """precision_90d, avg_return_45d, best/worst return, max_dd_post_signal."""

    class FakeAnalyzer:
        def __init__(self, signal_model):
            pass

        def generate_historical_signals(self, symbol, ohlc_df):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(["2022-01-10"]),
                    "combined_signal": [Signal.BUY],
                }
            )

    dates = pd.date_range("2022-01-01", periods=200, freq="D")
    close_vals = [100.0] * 200
    # Set exit at day 45 to +8% gain
    close_vals[54] = 108.0
    # Set exit at day 90 to +6% gain
    close_vals[99] = 106.0
    ohlc_df = pd.DataFrame(
        {
            "Open": close_vals,
            "High": close_vals,
            "Low": [v * 0.95 for v in close_vals],
            "Close": close_vals,
            "Volume": 1_000_000.0,
        },
        index=dates,
    )
    monkeypatch.setattr("dividend_tracker.backtest.StockDataAnalyzer", FakeAnalyzer)

    result = _evaluate_model(
        "lux",
        "TEST",
        ohlc_df,
        start_date="2022-01-01",
        end_date="2022-12-31",
    )

    assert result.total_signals == 1
    assert result.precision == 1.0
    assert result.precision_90d == 1.0
    assert result.avg_return_45d == pytest.approx(0.08, abs=0.01)
    assert result.best_signal_return == pytest.approx(0.08, abs=0.01)
    assert result.worst_signal_return == pytest.approx(0.08, abs=0.01)
    # combined_signals: price_ceiling=None means all signals pass through
    assert result.combined_signals == 1


def test_calculate_combined_signals_with_ceiling():
    dates = pd.date_range("2022-01-01", periods=10, freq="D")
    close_series = pd.Series([100.0] * 10, index=dates)
    signal_ts_below = pd.Timestamp("2022-01-05")  # entry=100, ceiling=110 -> below
    signal_ts_above = pd.Timestamp("2022-01-07")  # entry=100, ceiling=90 -> above

    # ceiling=110 — all signals pass
    count_all = calculate_combined_signals(
        [signal_ts_below], close_series, price_ceiling=110.0
    )
    assert count_all == 1

    # ceiling=90 — no signals pass (price 100 > 90)
    count_none = calculate_combined_signals(
        [signal_ts_above], close_series, price_ceiling=90.0
    )
    assert count_none == 0

    # ceiling=None — all signals pass regardless
    count_no_data = calculate_combined_signals(
        [signal_ts_below, signal_ts_above], close_series, price_ceiling=None
    )
    assert count_no_data == 2


def test_model_result_signals_per_year():
    m = ModelResult(
        model="lux",
        total_signals=10,
        precision=0.5,
        false_positive=0.1,
        neutral=0.4,
        max_drawdown=-0.05,
        period_start=date(2022, 1, 1),
        period_end=date(2024, 1, 1),
    )
    # 10 signals over ~2 years -> ~5 per year
    assert m.signals_per_year == pytest.approx(5.0, abs=0.1)
    # combined_signals=0 by default -> 0 per year
    assert m.combined_signals_per_year == pytest.approx(0.0, abs=0.01)


def test_write_report_includes_required_sections(tmp_path):
    output_path = tmp_path / "report_10y.md"
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
            period_signals={},
        )
    ]

    write_report(
        results,
        output_path=output_path,
        run_date=date(2026, 6, 10),
        yaml_updated=[],
        start_date="2016-01-01",
        end_date="2026-06-10",
    )

    report = output_path.read_text(encoding="utf-8")
    assert "# Backtest de pontos de entrada" in report
    assert "## Metodologia" in report
    assert "## Resumo executivo" in report
    assert "## Resultados detalhados por ativo" in report
    assert "## Análise de frequência" in report
    assert "## Análise de ciclos históricos" in report
    assert "## Decisões — atualização do YAML" in report
    assert "### EGIE3" in report
    # Recommended model line present
    assert "smc" in report
    assert "Gerado em: 2026-06-10" in report

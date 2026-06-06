import pandas as pd
from pandas.testing import assert_frame_equal

from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.signals import (
    AnalyzerSignalAdapter,
    LuxSignalGenerator,
    SignalGenerator,
    SMCSignalGenerator,
)


def test_load_local_data_reads_existing_csv_without_update(tmp_path):
    interval_dir = tmp_path / "1D"
    interval_dir.mkdir(parents=True)
    filepath = interval_dir / "AAPL.csv"
    expected = pd.DataFrame(
        {"Close": [10.0, 11.0], "Volume": [100, 200]},
        index=pd.to_datetime(["2026-04-19", "2026-04-20"]),
    )
    expected.to_csv(filepath)

    result = StockDataAnalyzer.load_local_data("AAPL", data_dir=tmp_path, interval="1d")

    assert_frame_equal(result, expected)


def test_load_local_data_raises_when_csv_does_not_exist(tmp_path):
    try:
        StockDataAnalyzer.load_local_data("AAPL", data_dir=tmp_path, interval="1d")
    except FileNotFoundError as exc:
        assert "Local CSV not found" in str(exc)
    else:
        raise AssertionError("Expected missing local CSV to raise FileNotFoundError")


def test_signal_generators_follow_adapter_contract():
    generators = [SignalGenerator(), LuxSignalGenerator(), SMCSignalGenerator()]

    assert all(isinstance(generator, AnalyzerSignalAdapter) for generator in generators)

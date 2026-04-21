import pandas as pd

from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.enums import Signal
from stock_analyzer.signals import RTSignalGenerator


def make_ohlc(rows: int = 90) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = pd.Series(
        [100 + i * 0.4 + ((i % 7) - 3) * 0.25 for i in range(rows)],
        index=index,
    )
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
        },
        index=index,
    )


def test_rt_signal_generator_returns_historical_columns():
    generator = RTSignalGenerator()

    result = generator.generate_historical_signals("AAPL", make_ohlc())

    expected_columns = {
        "date",
        "close",
        "supertrend",
        "trend",
        "adx",
        "is_strong",
        "upper_zone",
        "lower_zone",
        "rsi",
        "confirmation_buy",
        "confirmation_sell",
        "contrarian_buy",
        "contrarian_sell",
        "confirmation_signal",
        "contrarian_signal",
        "combined_signal",
    }
    assert expected_columns.issubset(result.columns)
    assert set(result["combined_signal"].dropna().unique()).issubset(
        {Signal.BUY, Signal.SELL, Signal.HOLD}
    )


def test_rt_signal_generator_returns_current_signal():
    generator = RTSignalGenerator()

    result = generator.generate_current_signal("AAPL", make_ohlc())

    assert result is not None
    assert result.symbol == "AAPL"
    assert result.combined_signal in {Signal.BUY, Signal.SELL, Signal.HOLD}


def test_stock_data_analyzer_can_select_rt_model():
    analyzer = StockDataAnalyzer(signal_model="rt")

    result = analyzer.generate_historical_signals("AAPL", make_ohlc())

    assert "supertrend" in result.columns
    assert "combined_signal" in result.columns

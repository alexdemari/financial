import pandas as pd
from pandas.testing import assert_frame_equal

from stock_data_manager.implementations.csv_reader import CSVReader
from stock_data_manager.implementations.csv_writer import CSVWriter


def test_csv_reader_returns_none_for_missing_file(tmp_path):
    result = CSVReader().read(tmp_path / "missing.csv")

    assert result is None


def test_csv_writer_and_reader_round_trip_dataframe(tmp_path):
    filepath = tmp_path / "nested" / "AAPL.csv"
    data = pd.DataFrame(
        {"Close": [10.0, 11.0], "Volume": [100, 200]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )

    CSVWriter().write(data, filepath)
    result = CSVReader().read(filepath)

    assert filepath.exists()
    assert_frame_equal(result, data)

"""
Tests for SqlitePriceDataRepository and CsvPriceDataRepository.

No network access. No real CSV files from the project required.
"""

import pandas as pd
import pytest

from stock_data_manager.repositories.csv_repository import CsvPriceDataRepository
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository
from stock_data_manager.implementations.sqlite_reader import SQLiteReader
from stock_data_manager.implementations.sqlite_writer import SQLiteWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ohlcv_df(n: int = 5, tz: str = "UTC") -> pd.DataFrame:
    """Return a small OHLCV DataFrame with a UTC DatetimeIndex."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz=tz)
    return pd.DataFrame(
        {
            "Open": [float(100 + i) for i in range(n)],
            "High": [float(101 + i) for i in range(n)],
            "Low": [float(99 + i) for i in range(n)],
            "Close": [float(100 + i) for i in range(n)],
            "Volume": [float(1_000_000 + i * 1000) for i in range(n)],
            "Dividends": [0.0] * n,
            "Stock Splits": [0.0] * n,
        },
        index=dates,
    )


def _db_path(tmp_path) -> str:
    return str(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_and_load_symbol_roundtrip(tmp_path):
    """Save a DataFrame, load it back, and assert equal values."""
    repo = SqlitePriceDataRepository(_db_path(tmp_path))
    df = make_ohlcv_df()

    repo.save_symbol("AAPL", df)
    loaded = repo.load_symbol("AAPL")

    expected_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Dividends",
        "Stock Splits",
    ]
    assert list(loaded.columns) == expected_columns
    assert len(loaded) == len(df)
    assert loaded.index.tz is not None  # must be tz-aware

    # Values must match
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert list(loaded[col]) == pytest.approx(list(df[col]))


def test_no_duplicate_rows_on_repeated_save(tmp_path):
    """Saving the same data twice must not create duplicate rows."""
    repo = SqlitePriceDataRepository(_db_path(tmp_path))
    df = make_ohlcv_df()

    repo.save_symbol("AAPL", df)
    repo.save_symbol("AAPL", df)

    loaded = repo.load_symbol("AAPL")
    assert len(loaded) == len(df)


def test_load_returns_correct_date_order(tmp_path):
    """Save rows in reverse chronological order; load must return ascending."""
    repo = SqlitePriceDataRepository(_db_path(tmp_path))

    df = make_ohlcv_df(n=5)
    df_reversed = df.iloc[::-1]

    repo.save_symbol("MSFT", df_reversed)
    loaded = repo.load_symbol("MSFT")

    assert list(loaded.index) == sorted(loaded.index)


def test_list_symbols_returns_all_saved(tmp_path):
    """list_symbols() must return every symbol that was saved."""
    repo = SqlitePriceDataRepository(_db_path(tmp_path))

    for symbol in ("AAPL", "MSFT", "GOOG"):
        repo.save_symbol(symbol, make_ohlcv_df())

    symbols = repo.list_symbols()
    assert sorted(symbols) == ["AAPL", "GOOG", "MSFT"]


def test_sqlite_repository_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "prices.db"
    repo = SqlitePriceDataRepository(str(db_path))

    repo.save_symbol("AAPL", make_ohlcv_df())

    assert db_path.exists()


def test_csv_and_sqlite_load_equivalent(tmp_path):
    """
    Create a minimal CSV, load via CsvPriceDataRepository, save to SQLite via
    SqlitePriceDataRepository, load back, and assert the DataFrames are equivalent.
    """
    # Build a CSV that matches the format expected by load_symbol_csv:
    # a 'Date' column (or similar), plus OHLCV columns.
    n = 5
    dates = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    df_original = pd.DataFrame(
        {
            "Open": [float(100 + i) for i in range(n)],
            "High": [float(101 + i) for i in range(n)],
            "Low": [float(99 + i) for i in range(n)],
            "Close": [float(100 + i) for i in range(n)],
            "Volume": [float(1_000_000 + i * 1000) for i in range(n)],
            "Dividends": [0.0] * n,
            "Stock Splits": [0.0] * n,
        },
        index=dates,
    )
    df_original.index.name = "Date"

    # Write CSV to tmp_path in the format load_symbol_csv expects:
    # index (Date) as the first column so the CSV has a "Date" column header.
    csv_path = tmp_path / "TSLA.csv"
    df_original.to_csv(csv_path)

    # Load via CsvPriceDataRepository (uses load_symbol_csv internally)
    csv_repo = CsvPriceDataRepository(str(tmp_path))
    df_from_csv = csv_repo.load_symbol("TSLA")

    # Save to SQLite and load back
    sqlite_repo = SqlitePriceDataRepository(_db_path(tmp_path))
    sqlite_repo.save_symbol("TSLA", df_from_csv)
    df_from_sqlite = sqlite_repo.load_symbol("TSLA")

    # Both must have the same length and Close values
    assert len(df_from_sqlite) == len(df_from_csv)

    csv_closes = sorted(float(v) for v in df_from_csv["Close"])
    sqlite_closes = sorted(float(v) for v in df_from_sqlite["Close"])
    assert csv_closes == pytest.approx(sqlite_closes)

    # Index must be tz-aware in both
    assert df_from_csv.index.tz is not None
    assert df_from_sqlite.index.tz is not None


def test_sqlite_reader_and_writer_use_symbol_from_filepath(tmp_path):
    db_path = str(tmp_path / "test.db")
    filepath = tmp_path / "AAPL.csv"
    df = make_ohlcv_df()

    writer = SQLiteWriter(db_path)
    reader = SQLiteReader(db_path)

    writer.write(df, filepath)
    loaded = reader.read(filepath)

    assert loaded is not None
    assert len(loaded) == len(df)
    assert list(loaded["Close"]) == pytest.approx(list(df["Close"]))

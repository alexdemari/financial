import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from stock_data_manager.repositories.base import PriceDataRepository

# Columns stored in ohlcv_daily mapped to their DataFrame names.
# The schema stores lowercase names; we surface them with original casing
# to match what load_symbol_csv returns from yfinance-written CSVs.
_DB_TO_DF_COLUMNS = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
    "dividends": "Dividends",
    "stock_splits": "Stock Splits",
}

_SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "sqlite_schema.sql"


def _get_col(df: pd.DataFrame, name: str):
    """Case-insensitive column lookup; returns None if column is absent."""
    lower_map = {c.lower(): c for c in df.columns}
    actual = lower_map.get(name.lower())
    if actual is None:
        return None
    return df[actual]


def _series_val(series, idx: int):
    """Return float value at position idx, or None if series is None or NaN."""
    if series is None:
        return None
    v = series.iloc[idx]
    return None if pd.isna(v) else float(v)


class SqlitePriceDataRepository(PriceDataRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        sql = _SCHEMA_PATH.read_text()
        with self._connect() as conn:
            conn.executescript(sql)

    # ------------------------------------------------------------------
    # PriceDataRepository interface
    # ------------------------------------------------------------------

    def load_symbol(self, symbol: str) -> pd.DataFrame:
        query = (
            "SELECT date, open, high, low, close, volume, dividends, stock_splits "
            "FROM ohlcv_daily WHERE symbol = ? ORDER BY date"
        )
        with self._connect() as conn:
            rows = conn.execute(query, (symbol,)).fetchall()

        if not rows:
            return pd.DataFrame(
                columns=list(_DB_TO_DF_COLUMNS.values()),
                index=pd.DatetimeIndex([], tz="UTC", name="Date"),
            )

        dates = [row[0] for row in rows]
        data = {
            "Open": [row[1] for row in rows],
            "High": [row[2] for row in rows],
            "Low": [row[3] for row in rows],
            "Close": [row[4] for row in rows],
            "Volume": [row[5] for row in rows],
            "Dividends": [row[6] for row in rows],
            "Stock Splits": [row[7] for row in rows],
        }

        index = pd.to_datetime(dates, utc=True)
        index.name = "Date"
        df = pd.DataFrame(data, index=index)
        return df

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        imported_at = datetime.now(tz=timezone.utc).isoformat()

        open_col = _get_col(df, "open")
        high_col = _get_col(df, "high")
        low_col = _get_col(df, "low")
        close_col = _get_col(df, "close")
        volume_col = _get_col(df, "volume")
        dividends_col = _get_col(df, "dividends")
        splits_col = _get_col(df, "stock splits")
        if splits_col is None:
            splits_col = _get_col(df, "stock_splits")

        rows = []
        for i, date_val in enumerate(df.index):
            date_str = pd.Timestamp(date_val).isoformat()
            rows.append(
                (
                    symbol,
                    date_str,
                    _series_val(open_col, i),
                    _series_val(high_col, i),
                    _series_val(low_col, i),
                    _series_val(close_col, i),
                    _series_val(volume_col, i),
                    _series_val(dividends_col, i),
                    _series_val(splits_col, i),
                    None,  # source
                    imported_at,
                )
            )

        sql = (
            "INSERT OR REPLACE INTO ohlcv_daily "
            "(symbol, date, open, high, low, close, volume, dividends, stock_splits, source, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        with self._connect() as conn:
            conn.executemany(sql, rows)

    def list_symbols(self) -> list[str]:
        query = "SELECT DISTINCT symbol FROM ohlcv_daily ORDER BY symbol"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [row[0] for row in rows]

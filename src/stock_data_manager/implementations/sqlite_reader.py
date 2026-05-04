import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from stock_data_manager.interfaces.data_reader import IDataReader
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository


class SQLiteReader(IDataReader):
    """Read symbol OHLCV data from a local SQLite database."""

    def __init__(self, db_path: str):
        self.repository = SqlitePriceDataRepository(db_path)
        self.logger = logging.getLogger(self.__class__.__name__)

    def read(self, filepath: Path) -> Optional[pd.DataFrame]:
        symbol = filepath.stem
        df = self.repository.load_symbol(symbol)
        if df.empty:
            self.logger.info("SQLite data not found for %s", symbol)
            return None

        self.logger.info("SQLite data read: %d rows for %s", len(df), symbol)
        return df

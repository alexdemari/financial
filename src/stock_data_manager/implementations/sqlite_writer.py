import logging
from pathlib import Path

import pandas as pd

from stock_data_manager.interfaces.data_writer import IDataWriter
from stock_data_manager.repositories.sqlite_repository import SqlitePriceDataRepository


class SQLiteWriter(IDataWriter):
    """Write symbol OHLCV data to a local SQLite database."""

    def __init__(self, db_path: str):
        self.repository = SqlitePriceDataRepository(db_path)
        self.logger = logging.getLogger(self.__class__.__name__)

    def write(self, data: pd.DataFrame, filepath: Path) -> None:
        symbol = filepath.stem
        self.repository.save_symbol(symbol, data)
        self.logger.info("SQLite data saved: %d rows for %s", len(data), symbol)

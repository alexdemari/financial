from stock_data_manager.implementations.csv_reader import CSVReader
from stock_data_manager.implementations.csv_writer import CSVWriter
from stock_data_manager.implementations.sqlite_reader import SQLiteReader
from stock_data_manager.implementations.sqlite_writer import SQLiteWriter
from stock_data_manager.implementations.yfinance_downloader import YFinanceDownloader
from stock_data_manager.managers.stock_data_manager import StockDataManager
from stock_data_manager.strategies.append_merge import AppendMergeStrategy
from stock_data_manager.strategies.update_merge import UpdateMergeStrategy


class StockDataManagerFactory:
    @staticmethod
    def create_default(
        data_dir: str = "data/1D",
        storage: str = "csv",
        db_path: str = "data/financial.db",
    ) -> StockDataManager:
        reader, writer = StockDataManagerFactory._create_storage(storage, db_path)
        return StockDataManager(
            reader=reader,
            writer=writer,
            downloader=YFinanceDownloader(),
            merge_strategy=AppendMergeStrategy(),
            data_dir=data_dir,
        )

    @staticmethod
    def create_with_update_strategy(
        data_dir: str = "data/stocks/1D",
        storage: str = "csv",
        db_path: str = "data/financial.db",
    ) -> StockDataManager:
        reader, writer = StockDataManagerFactory._create_storage(storage, db_path)
        return StockDataManager(
            reader=reader,
            writer=writer,
            downloader=YFinanceDownloader(),
            merge_strategy=UpdateMergeStrategy(),
            data_dir=data_dir,
        )

    @staticmethod
    def _create_storage(storage: str, db_path: str):
        if storage == "csv":
            return CSVReader(), CSVWriter()
        if storage == "sqlite":
            return SQLiteReader(db_path), SQLiteWriter(db_path)
        raise ValueError(f"Unsupported storage backend: {storage}")

from stock_data_manager.implementations.csv_reader import CSVReader
from stock_data_manager.implementations.csv_writer import CSVWriter
from stock_data_manager.implementations.yfinance_downloader import YFinanceDownloader
from stock_data_manager.managers.stock_data_manager import StockDataManager
from stock_data_manager.strategies.append_merge import AppendMergeStrategy
from stock_data_manager.strategies.update_merge import UpdateMergeStrategy


class StockDataManagerFactory:
    @staticmethod
    def create_default(data_dir: str = "data/stocks") -> StockDataManager:
        return StockDataManager(
            reader=CSVReader(),
            writer=CSVWriter(),
            downloader=YFinanceDownloader(),
            merge_strategy=AppendMergeStrategy(),
            data_dir=data_dir,
        )

    @staticmethod
    def create_with_update_strategy(data_dir: str = "data/stocks") -> StockDataManager:
        return StockDataManager(
            reader=CSVReader(),
            writer=CSVWriter(),
            downloader=YFinanceDownloader(),
            merge_strategy=UpdateMergeStrategy(),
            data_dir=data_dir,
        )

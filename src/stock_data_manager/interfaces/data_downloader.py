import pandas as pd

from abc import ABC, abstractmethod

from stock_data_manager.models.stock_config import StockConfig


# Interface Segregation Principle (I)
class IDataDownloader(ABC):
    """Interface para download de dados"""

    @abstractmethod
    def download(self, config: StockConfig) -> pd.DataFrame:
        pass

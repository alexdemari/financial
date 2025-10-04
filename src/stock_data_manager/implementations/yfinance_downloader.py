import logging
import pandas as pd
import yfinance as yf

from stock_data_manager.interfaces.data_downloader import IDataDownloader
from stock_data_manager.models.stock_config import StockConfig


class YFinanceDownloader(IDataDownloader):
    """Responsável apenas por baixar dados do Yahoo Finance"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def download(self, config: StockConfig) -> pd.DataFrame:
        try:
            self.logger.info(
                f"Baixando {config.symbol} de {config.start_date} até {config.end_date}"
            )

            ticker = yf.Ticker(config.symbol)
            df = ticker.history(
                start=config.start_date, end=config.end_date, interval=config.interval
            )

            if df.empty:
                self.logger.warning(f"Nenhum dado retornado para {config.symbol}")
            else:
                self.logger.info(f"Baixados {len(df)} registros para {config.symbol}")

            return df
        except Exception as e:
            self.logger.error(f"Erro ao baixar {config.symbol}: {e}")
            raise

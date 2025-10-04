import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import pandas as pd

from stock_data_manager.interfaces.data_downloader import IDataDownloader
from stock_data_manager.interfaces.data_reader import IDataReader
from stock_data_manager.interfaces.data_writer import IDataWriter
from stock_data_manager.interfaces.merge_strategy import IMergeStrategy
from stock_data_manager.models.stock_config import StockConfig


class StockDataManager:
    def __init__(
        self,
        reader: IDataReader,
        writer: IDataWriter,
        downloader: IDataDownloader,
        merge_strategy: IMergeStrategy,
        data_dir: str = "data/stocks",
    ):
        self.reader = reader
        self.writer = writer
        self.downloader = downloader
        self.merge_strategy = merge_strategy
        self.data_dir = Path(data_dir)
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_filepath(self, symbol: str) -> Path:
        return self.data_dir / f"{symbol}.csv"

    def _calculate_start_date(self, existing_data: Optional[pd.DataFrame]) -> str:
        if existing_data is None or existing_data.empty:
            # Se não há dados, baixa dos últimos 10 anos
            start = datetime.now() - timedelta(days=10 * 365)
            return start.strftime("%Y-%m-%d")

        # Pega o último dia disponível e adiciona 1 dia
        last_date = existing_data.index.max()
        next_date = last_date + timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")

    def download_and_save(self, symbol: str, force_full: bool = False) -> pd.DataFrame:
        filepath = self._get_filepath(symbol)

        existing_data = None if force_full else self.reader.read(filepath)

        start_date = self._calculate_start_date(existing_data)

        if not force_full and existing_data is not None:
            last_date = existing_data.index.max().strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")

            if last_date >= today:
                self.logger.info(f"{symbol} já está atualizado até {last_date}")
                return existing_data

        config = StockConfig(symbol=symbol, start_date=start_date)
        new_data = self.downloader.download(config)

        if new_data.empty:
            self.logger.info(f"Nenhum dado novo para {symbol}")
            return existing_data if existing_data is not None else new_data

        if existing_data is not None and not existing_data.empty:
            final_data = self.merge_strategy.merge(existing_data, new_data)
            self.logger.info(f"Dados mesclados: {len(final_data)} registros totais")
        else:
            final_data = new_data

        self.writer.write(final_data, filepath)

        return final_data

    def download_multiple(self, symbols: List[str], force_full: bool = False) -> dict:
        results = {}

        for symbol in symbols:
            try:
                self.logger.info(f"Processando {symbol}...")
                results[symbol] = self.download_and_save(symbol, force_full)
            except Exception as e:
                self.logger.error(f"Erro ao processar {symbol}: {e}")
                results[symbol] = None

        return results

    def get_data(self, symbol: str) -> Optional[pd.DataFrame]:
        filepath = self._get_filepath(symbol)
        return self.reader.read(filepath)

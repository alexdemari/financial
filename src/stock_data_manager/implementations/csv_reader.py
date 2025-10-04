from pathlib import Path
from typing import Optional
import pandas as pd
import logging

from stock_data_manager.interfaces.data_reader import IDataReader


# Single Responsibility Principle (S)
class CSVReader(IDataReader):
    """Responsável apenas por ler arquivos CSV"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def read(self, filepath: Path) -> Optional[pd.DataFrame]:
        try:
            if not filepath.exists():
                self.logger.info(f"Arquivo não encontrado: {filepath}")
                return None

            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            self.logger.info(f"Dados lidos: {len(df)} registros de {filepath}")
            return df
        except Exception as e:
            self.logger.error(f"Erro ao ler {filepath}: {e}")
            return None

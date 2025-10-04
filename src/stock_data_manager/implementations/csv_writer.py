from pathlib import Path
import pandas as pd
import logging

from stock_data_manager.interfaces.data_writer import IDataWriter


class CSVWriter(IDataWriter):
    """Responsável apenas por escrever arquivos CSV"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def write(self, data: pd.DataFrame, filepath: Path) -> None:
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(filepath)
            self.logger.info(f"Dados salvos: {len(data)} registros em {filepath}")
        except Exception as e:
            self.logger.error(f"Erro ao salvar {filepath}: {e}")
            raise

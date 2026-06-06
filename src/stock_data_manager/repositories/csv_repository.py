from pathlib import Path

import pandas as pd

from market_scanner.eligibility import load_symbol_csv
from stock_data_manager.repositories.base import PriceDataRepository


class CsvPriceDataRepository(PriceDataRepository):
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def load_symbol(self, symbol: str) -> pd.DataFrame:
        return load_symbol_csv(self.data_dir, symbol)

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        path = Path(self.data_dir) / f"{symbol}.csv"
        df.to_csv(path)

    def list_symbols(self) -> list[str]:
        return [p.stem for p in Path(self.data_dir).glob("*.csv")]

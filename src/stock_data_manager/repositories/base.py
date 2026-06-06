import pandas as pd


class PriceDataRepository:
    def load_symbol(self, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    def save_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        raise NotImplementedError

    def list_symbols(self) -> list[str]:
        raise NotImplementedError

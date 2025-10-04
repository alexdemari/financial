import pandas as pd

from stock_data_manager.interfaces.merge_strategy import IMergeStrategy


class UpdateMergeStrategy(IMergeStrategy):
    """Estratégia que atualiza dados existentes com novos valores"""

    def merge(self, existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        existing.update(new)
        combined = pd.concat([existing, new])
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined.sort_index()

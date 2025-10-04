import pandas as pd

from stock_data_manager.interfaces.merge_strategy import IMergeStrategy


class AppendMergeStrategy(IMergeStrategy):
    """Estratégia que adiciona novos dados e remove duplicatas"""

    def merge(self, existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        combined = pd.concat([existing, new])
        combined = combined[~combined.index.duplicated(keep="last")]
        return combined.sort_index()

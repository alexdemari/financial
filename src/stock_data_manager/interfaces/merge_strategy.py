import pandas as pd

from abc import ABC, abstractmethod


# Interface Segregation Principle (I)
class IMergeStrategy(ABC):
    @abstractmethod
    def merge(self, existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        pass

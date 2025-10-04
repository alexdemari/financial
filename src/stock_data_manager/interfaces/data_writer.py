import pandas as pd

from pathlib import Path
from abc import ABC, abstractmethod


# Interface Segregation Principle (I)
class IDataWriter(ABC):
    """Interface para escrita de dados"""

    @abstractmethod
    def write(self, data: pd.DataFrame, filepath: Path) -> None:
        pass

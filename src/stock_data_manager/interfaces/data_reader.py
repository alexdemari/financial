from typing import Optional

import pandas as pd

from pathlib import Path
from abc import ABC, abstractmethod


# Interface Segregation Principle (I)
class IDataReader(ABC):
    @abstractmethod
    def read(self, filepath: Path) -> Optional[pd.DataFrame]:
        pass

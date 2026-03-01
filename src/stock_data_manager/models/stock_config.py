from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dateutil import relativedelta


@dataclass
class StockConfig:
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    interval: str = "1d"

    def __post_init__(self):
        if self.end_date is None:
            self.end_date = (
                datetime.now() + relativedelta.relativedelta(days=1)
            ).strftime("%Y-%m-%d")

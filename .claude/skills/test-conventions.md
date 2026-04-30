# Skill: Test Conventions

Project-specific rules for writing tests in this codebase.

---

## Framework & Runner

```bash
uv run pytest
.venv/bin/python -m pytest tests/<module>   # targeted
```

---

## Hard Rules

- **No network** — mock `yfinance` at `stock_data_manager.downloader.yf`
- **No filesystem reads** — build DataFrames in memory; never load real CSVs
- **Mock only external boundaries** — not internal functions
- **Test behavior** — not implementation details

---

## OHLC Fixture (canonical)

```python
import pandas as pd
import numpy as np

def make_ohlcv(n: int = 100) -> pd.DataFrame:
    """Minimal OHLC fixture. n >= 50 required for SMC."""
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    close = 100.0 + np.cumsum(np.random.randn(n))
    return pd.DataFrame({
        "Open":   close * 0.99,
        "High":   close * 1.01,
        "Low":    close * 0.98,
        "Close":  close,
        "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
    }, index=dates)
```

- Index must be `DatetimeIndex` — never string
- Minimum 50 bars for SMC; 100 recommended
- Column names capitalized: `Open`, `High`, `Low`, `Close`, `Volume`

---

## Mocking yfinance

```python
from unittest.mock import patch

@patch("stock_data_manager.downloader.yf.download")
def test_download(mock_download):
    mock_download.return_value = make_ohlcv(200)
    # ...
```

---

## Coverage Minimum Per Module

| Scenario | Required |
|---|---|
| Happy path | ✅ |
| Empty DataFrame | ✅ |
| Insufficient bars (< 50) | ✅ |
| Missing columns | ✅ |
| CLI flags (if applicable) | ✅ |

---

## File Naming

```
tests/
  stock_data_manager/
    test_csv_repository.py
    test_downloader.py
  stock_analyzer/
    test_lux_model.py
    test_smc_model.py
  market_scanner/
    test_scanner_row.py
    test_eligibility.py
    test_backtest.py
```

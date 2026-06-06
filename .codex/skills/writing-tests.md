---
name: writing-tests
description: >
  Writes behavior-oriented unit tests for Python modules in this project.
  Use when asked to add tests, improve coverage, implement features that
  require tests, or when working with stock_analyzer, market_scanner,
  trading_indicators, or stock_data_manager modules.
---

# Writing Tests

## Runner

```bash
uv run pytest
uv run pytest tests/<module> -v   # targeted
```

## Hard rules

- No network — mock `yfinance` at `stock_data_manager.downloader.yf`
- No real CSV reads — build DataFrames in memory
- Mock only external boundaries (network, filesystem), not internal functions
- Test behavior, not implementation details

## Canonical OHLC fixture

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

- Index: `DatetimeIndex` always — never string
- Minimum 50 bars for SMC; 100 recommended
- Columns capitalized: `Open High Low Close Volume`

## Mocking yfinance

```python
from unittest.mock import patch

@patch("stock_data_manager.downloader.yf.download")
def test_something(mock_dl):
    mock_dl.return_value = make_ohlcv(200)
```

## Coverage minimum per module

| Scenario | Required |
|---|---|
| Happy path | ✅ |
| Empty DataFrame | ✅ |
| Insufficient bars (< 50) | ✅ |
| Missing columns | ✅ |
| CLI flags (if applicable) | ✅ |

## File naming

```
tests/stock_data_manager/test_csv_repository.py
tests/stock_analyzer/test_lux_model.py
tests/stock_analyzer/test_smc_model.py
tests/market_scanner/test_scanner_row.py
tests/market_scanner/test_eligibility.py
tests/market_scanner/test_backtest.py
```

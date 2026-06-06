---
name: caching-calculations
description: >
  Implements disk-based cache for Lux/SMC calculations in market_scanner.
  Use when adding cache.py to market_scanner, implementing --no-cache flag,
  or when asked to avoid recomputing indicators on repeated runs.
---

# Caching Calculations

## Cache key strategy

Key is `(symbol, csv_mtime)` — invalidates automatically when CSV changes:

```python
from pathlib import Path

def cache_key(symbol: str, csv_path: Path) -> str:
    mtime = int(csv_path.stat().st_mtime)
    return f"{symbol}_{mtime}"
```

## Read/write pattern

```python
import pandas as pd
from pathlib import Path

CACHE_DIR = Path("data/cache")

def load_cached(symbol: str, csv_path: Path, subdir: str) -> pd.DataFrame | None:
    key = cache_key(symbol, csv_path)
    path = CACHE_DIR / subdir / f"{key}.pkl"
    if path.exists():
        try:
            return pd.read_pickle(path)
        except Exception:
            path.unlink(missing_ok=True)   # corrupt cache — discard silently
    return None

def save_cache(symbol: str, csv_path: Path, df: pd.DataFrame, subdir: str) -> None:
    key = cache_key(symbol, csv_path)
    path = CACHE_DIR / subdir / f"{key}.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
```

## Usage in scanner

```python
def get_lux_history(symbol, df, csv_path, use_cache=True):
    if use_cache:
        cached = load_cached(symbol, csv_path, "lux")
        if cached is not None:
            return cached
    result = compute_lux(df)          # existing call
    if use_cache:
        save_cache(symbol, csv_path, result, "lux")
    return result
```

## Rules

- Cache miss or error → silently recompute, never raise
- `--no-cache` flag disables completely; default is enabled
- `data/cache/` must be in `.gitignore`
- No new dependencies — use `pickle` via `pd.to_pickle` / `pd.read_pickle`
- Do not cache scanner row decisions — only indicator histories (Lux, SMC)

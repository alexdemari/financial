---
name: parallelizing-scanner
description: >
  Implements parallel symbol processing in market_scanner using ProcessPoolExecutor.
  Use when adding --workers flag to scan.py, backtest.py, or backtest_execution.py,
  or when asked to parallelize any per-symbol loop in market_scanner.
---

# Parallelizing Scanner

## Pattern — ProcessPoolExecutor only

```python
from concurrent.futures import ProcessPoolExecutor
from typing import Any

def _worker(args: tuple) -> dict:
    """Top-level function — required for pickling in multiprocessing."""
    symbol, df, config = args
    return build_scanner_row(symbol, df, config)

def run_parallel(symbol_args: list[tuple], workers: int) -> list[dict]:
    if workers == 1:
        return [_worker(a) for a in symbol_args]   # no overhead
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_worker, symbol_args))
```

## Rules

- **Load before pool** — CSV loading happens in the main process; workers receive DataFrames already in memory
- **No shared state** — workers are isolated; no globals, no shared cache between workers
- **Top-level worker function** — worker must be defined at module top level (not nested), or pickling fails on Windows/WSL
- **`--workers 1` is default** — behavior must be identical to current with 1 worker
- **Caller stays sync** — parallelism is internal; the function signature doesn't change

## CLI flag pattern

```python
parser.add_argument("--workers", type=int, default=1,
    help="Number of parallel workers for symbol processing (default: 1)")
```

## Error handling

Worker errors must not crash the full run:

```python
def _worker(args):
    symbol, df, config = args
    try:
        return build_scanner_row(symbol, df, config)
    except Exception as e:
        return {"symbol": symbol, "eligible": False, "excluded_reason": str(e)}
```

## What NOT to do

- No `asyncio`, `threading`, or queues
- No I/O inside workers (no CSV reads, no pickle writes)
- No shared mutable state between workers

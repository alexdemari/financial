# Prompts de sessão

Um prompt por task. Use o bloco correspondente ao ambiente:
- **Codex**: entregue o prompt completo de uma vez (one-shot)
- **Claude Code**: use como abertura de sessão, depois itere

---

## Task 01 — Profiling de escala real

```
Implement the profiling task described in docs/ai/tasks/01-profiling-escala-real.md.

Do not modify any production code. Create a standalone profiling script at
scripts/profile_scanner.py that:
1. Runs the scanner with 5+ real symbols from data/scanner_universe_sample.csv, 260 bars
2. Uses cProfile to measure time per phase: CSV loading, Lux calc, SMC calc, build_scanner_row, output
3. Prints a report with top 20 functions by cumulative time
4. Saves the report to reports/profiling/scanner_profile_<date>.txt

After running, answer: is the bottleneck I/O (CSV loading) or CPU (indicator calculation)?

Constraints:
- stdlib only: cProfile, pstats, time
- No production code changes
- Run with: PYTHONPATH=src uv run python scripts/profile_scanner.py
```

---

## Task 02 — SQLite data layer

```
Implement the task described in docs/ai/tasks/introduce-sqlite-data-layer.md.
Use the adding-features skill.

After implementing, verify:
  PYTHONPATH=src uv run python -m stock_data_manager.importers.csv_to_sqlite \
    --data-dir data/stocks/1D --db-path /tmp/test.db --symbols AAPL
  uv run pytest tests/stock_data_manager

Constraints:
1. load_symbol_csv() must continue working exactly as today
2. No changes to stock_analyzer, market_scanner, or trading_indicators
3. sqlite3 stdlib only — no SQLAlchemy, no external DB
4. CSV remains the default — SQLite is opt-in
```

---

## Task 03 — Paralelização

```
Implement the task described in docs/ai/tasks/03-paralelizacao-scanner-backtest.md.
Use the parallelizing-scanner skill.

Apply to: market_scanner/scan.py, backtest.py, backtest_execution.py

After implementing, verify:
  uv run pytest tests/market_scanner
  just market-scanner                    # workers=1, identical to current output
  just market-scanner workers=4          # faster for large universe

Constraints:
1. --workers 1 must produce bit-identical output to current behavior
2. Workers receive DataFrames already loaded — no I/O inside workers
3. ProcessPoolExecutor only — no asyncio, threading, or queues
4. Worker function must be at module top level (not nested)
5. Worker errors must not crash the full run — use excluded_reason pattern
```

---

## Task 04 — Cache de cálculos

```
Implement the task described in docs/ai/tasks/04-cache-calculos-disco.md.
Use the caching-calculations skill.

Create src/market_scanner/cache.py and integrate with scan.py and backtest.py.

After implementing, verify:
  just market-scanner                    # first run — populates cache
  just market-scanner                    # second run — faster
  touch data/stocks/1D/AAPL.csv
  just market-scanner                    # AAPL recomputed, rest from cache
  uv run pytest tests/market_scanner

Constraints:
1. Cache miss or corruption → silent fallback to recomputation, never raise
2. --no-cache flag disables completely
3. data/cache/ must be added to .gitignore
4. No new dependencies — pd.to_pickle / pd.read_pickle only
5. Cache only indicator histories (Lux, SMC) — never scanner row decisions
```

---

## Task 05 — LLM Explainer

```
Implement the task described in docs/ai/tasks/05-llm-explainer.md.
Use the adding-llm-explainer skill.

Create src/market_scanner/llm/__init__.py, explainer.py, and prompts.py.
Integrate --explain flag into market_scanner/scan.py.

After implementing, verify:
  ANTHROPIC_API_KEY=<key> just market-scanner explain=true
  head -2 reports/market_scanner/scan.csv   # must have 'explanation' column
  just market-scanner explain=true           # without API key — must not crash
  uv run pytest tests/market_scanner

Constraints:
1. Without --explain: zero behavior change, zero performance impact
2. LLM failure (no key, timeout, error) → empty string, run continues
3. Post-scan only — never influences scanner decisions
4. Target: market_scanner/llm/ — not options_tech_scanner
5. Use claude-haiku-4-5 as default model
```

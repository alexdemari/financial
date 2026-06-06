# Context Map

Quick reference for navigating the codebase. Use this before asking "which file owns X?"

---

## Module → Directory

```
stock_data_manager   →  src/stock_data_manager/
stock_analyzer       →  src/stock_analyzer/
trading_indicators   →  src/trading_indicators/
market_scanner       →  src/market_scanner/
options_tech_scanner →  src/options_tech_scanner/   (legacy, do not extend)
```

---

## Key Entry Points

| What | Where |
|---|---|
| Download / update data | `src/stock_data_manager/main.py` |
| Analyze one symbol | `src/stock_analyzer/main.py` |
| Run scanner | `src/market_scanner/scan.py` |
| Run backtest | `src/market_scanner/backtest.py` |
| Run execution backtest | `src/market_scanner/backtest_execution.py` |
| Generate operational report (backtest analysis) | `src/market_scanner/operational_report.py` |
| Generate daily actionable report (fresh signals + top candidates) | `src/market_scanner/daily_report.py` |
| Run performance benchmark | `src/bench.py` |

---

## Most Important Shared Artifact

```
market_scanner.scanner_row
```

This is the source of truth for Scanner V3 decisions.
Both live scan and backtest consume it.
If you change it, both change.

---

## Data Flow

```
data/stocks/1D/<SYMBOL>.csv
    ↓
stock_data_manager (load_symbol_csv)
    ↓
stock_analyzer (lux_role, smc_role, signal)
    ↓
market_scanner.scanner_row (alignment, market_state, action_bucket)
    ↓
market_scanner.scan → reports/market_scanner/scan_daily.csv
    ↓
market_scanner.backtest_execution → reports/market_scanner/execution_recommended_rules.csv
    ↓
market_scanner.daily_report → reports/market_scanner/daily_report.md
                               reports/market_scanner/daily_candidates.csv
```

`execution_recommended_rules.csv` is regenerated periodically (e.g. weekly), not daily.
`daily_report` consumes both `scan_daily.csv` and `execution_recommended_rules.csv` as inputs.

---

## Test Layout

```
tests/
  stock_data_manager/
  stock_analyzer/
  market_scanner/
  options_tech_scanner/
```

---

## Docs Layout

```
docs/
  architecture/   ←  current state only
  adr/            ←  architectural decisions (ADR-001, ADR-002)
  ai/
    tasks/        ←  scoped work items (one per feature)
    skills/       ←  how-to guides for Codex sessions
    prompts/      ←  prompt templates for Codex
    playbooks/    ←  session workflows
  product/
  runbooks/
```

---

## Claude Code Layout

```
.claude/
  settings.json   ←  hooks + model config
  agents/         ←  subagents (code-reviewer, test-writer, backtest-validator)
  skills/         ←  domain knowledge (building-scanner-rows, writing-tests,
                      accessing-local-data, adding-features, reviewing-code,
                      validating-backtest, building-daily-operational-report,
                      parallelizing-scanner, caching-calculations)
  commands/       ←  slash commands (/review, /tests, /feature)
  hooks/          ←  block_dangerous.py, session_summary.py

.codex/
  skills/         ←  mirror of .claude/skills/ (kept in sync via just sync-skills)
```

---

## Daily Operational Workflow

```bash
# 1. Update local data
PYTHONPATH=src uv run python -m stock_data_manager.main -s <universe>

# 2. Run scanner (cache active)
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output reports/market_scanner/scan_daily.csv --workers 8

# 3. Generate daily report
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --max-days 2 --top 20 \
  --output reports/market_scanner/daily_report.md

# Periodic (weekly): regenerate execution_recommended_rules.csv via backtest_execution
```

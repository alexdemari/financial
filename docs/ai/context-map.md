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
| Generate operational report | `src/market_scanner/operational_report.py` |

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
market_scanner.scan → reports/market_scanner/scan.csv
    ↓
market_scanner.backtest → reports/market_scanner/backtest_*.csv
```

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
  skills/         ←  domain knowledge (scanner-patterns, test-conventions, data-access)
  commands/       ←  slash commands (/review, /tests, /feature)
  hooks/          ←  block_dangerous.py, session_summary.py
```

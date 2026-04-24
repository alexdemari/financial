# AGENT.md

## Project Purpose

This is a local-first Python project for financial data collection and analysis.

Main modules:

- `stock_data_manager`: historical market data ingestion and persistence
- `stock_analyzer`: analysis of persisted data and signal generation
- `trading_indicators`: reusable indicators and signal models
- `options_tech_scanner`: options-based strategy evaluation

---

## Current Architecture State

- Modular monolith
- CLI-driven execution
- Batch-oriented workflows
- CSV-based persistence
- pandas as in-memory representation

The system is NOT:

- event-driven
- distributed
- real-time

---

## Current Priorities

1. Stabilize local/manual workflows
2. Improve module boundaries
3. Expand and strengthen unit tests
4. Keep architecture simple and explicit
5. Avoid premature infrastructure (Redis, queues, async)

---

## Architectural Principles

- Prefer simplicity over abstraction
- Keep flows explicit and predictable
- Separate concerns:
  - data collection (`stock_data_manager`)
  - analysis (`stock_analyzer`)
- Reuse `trading_indicators` instead of duplicating logic
- Avoid tight coupling between modules
- Design for future evolution, but implement only what is needed now

---

## Rules For Changes

- Do NOT introduce:
  - Redis
  - event buses
  - async processing
  - distributed systems

- Do NOT:
  - refactor unrelated modules
  - redesign architecture unless explicitly requested
  - duplicate logic already available in shared modules

- Always:
  - keep changes incremental
  - preserve existing behavior unless explicitly changing it
  - update tests when behavior changes
  - update README/CLI help when UX changes

---

## CLI Behavior Expectations

- CLI must be predictable and explicit
- Avoid implicit side effects
- Separate flows clearly (e.g., analyze vs update)

---

## Testing Guidelines

- Prefer unit tests without network access
- Use in-memory DataFrames
- Mock only external boundaries (e.g., yfinance)
- Test behavior, not implementation details
- Add regression tests for CLI flags and workflows

---

## Documentation Rules

- Architecture docs must reflect actual implementation
- Future concepts must be clearly marked
- Do NOT mix current and future state in the same document

---

## Environment

Primary environment: WSL / Ubuntu

Use:

```bash
uv run pytest
.venv/bin/python -m pytest
```

When working from Windows against this repo:

- prefer running test/lint/commit flows through `wsl bash -lc "..."`
- if `git commit` depends on hooks/pre-commit from the Linux `.venv`, do NOT commit from plain PowerShell
- use this commit flow:

```bash
wsl bash -lc "cd /mnt/c/Users/alexa/Documents/development/financial && git commit -m '...'"
```

- if `ruff-format` or another hook rewrites files during commit:
  - review the changes
  - re-stage the modified files
  - re-run the same `wsl` commit command

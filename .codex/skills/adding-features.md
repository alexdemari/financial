---
name: adding-features
description: >
  Implements new features in this project with minimal scope and no side effects.
  Use when adding CLI flags, new analysis models, scanner improvements, backtest
  enhancements, or any behavioral change to existing modules. Always produces
  code + tests + documentation update.
---

# Adding Features

## Constraints — always apply

1. Keep scope strictly limited to the task — no unrelated refactors
2. Preserve existing behavior unless explicitly changing it
3. No Redis, async, queues, external DBs, or infra
4. No duplicate indicator logic — reuse `trading_indicators`
5. Do not modify scanner/analyzer boundary without explicit instruction

## Outcome spec pattern (preferred over HOW instructions)

State what must be true when done:

```
Goal: <one clear behavior change>
Constraints:
  1. <what must not change>
  2. <what must not change>
  3. Tests must pass: uv run pytest tests/<module>
Verification: <how to confirm it works>
```

## Steps

1. Read the relevant task file from `docs/ai/tasks/` if one exists
2. Inspect current behavior in impacted modules
3. Implement the minimal change
4. Add tests covering: happy path, edge cases, failure path
5. Update README/CLI help if behavior is user-visible
6. Run: `uv run pytest && uv run ruff check src tests`

## Module boundaries — check before touching

```
stock_data_manager   owns: download, CSV persistence
stock_analyzer       owns: single-symbol signal generation
trading_indicators   owns: raw Lux/SMC calculations
market_scanner       owns: multi-symbol orchestration, Scanner V3 decisions
```

If a change touches more than one module, propose a plan first.

## Definition of done

- Code implemented
- Tests pass (`uv run pytest`)
- Lint passes (`uv run ruff check src tests`)
- README/CLI help updated if behavior changed
- No changes outside the stated scope

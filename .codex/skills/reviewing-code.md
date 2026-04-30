---
name: reviewing-code
description: >
  Reviews code changes for correctness, architecture compliance, and test quality
  in this project. Use when reviewing a diff, pull request, recent commit, or when
  asked to check if changes respect module boundaries, test coverage, or project rules.
---

# Reviewing Code

## What to check

**1. Module boundaries**
- Does `market_scanner` contain any Lux/SMC indicator logic? → MUST FIX
- Does `stock_analyzer` do multi-symbol work? → MUST FIX
- Does any analysis module call yfinance directly? → MUST FIX

**2. Tests**
- No network access in tests (yfinance must be mocked)
- DataFrames built in memory, not loaded from CSV
- Tests validate behavior, not just that functions were called

**3. Correctness**
- Edge cases: empty DataFrame, < 50 bars, missing columns
- DatetimeIndex used, never string index
- Scanner row fields match canonical schema

**4. Scope**
- Did changes touch files outside the stated task?
- Were unrelated modules refactored? → flag as unintended change

**5. Documentation**
- If CLI behavior changed: is README updated?
- If module boundary changed: is architecture doc updated?

## Output format

```
MUST FIX:
- <specific issue, file and line if possible>

SHOULD FIX:
- <issue that matters but won't break immediately>

CONSIDER:
- <optional improvement>

SAFE TO KEEP:
- <confirmed correct sections>
```

Be specific. Financial data — correctness matters.

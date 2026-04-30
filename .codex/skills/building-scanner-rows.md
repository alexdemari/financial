---
name: building-scanner-rows
description: >
  Builds and modifies Scanner V3 rows in market_scanner. Use when working
  with scanner row construction, alignment logic, market_state classification,
  action_bucket assignment, or the decision layer in market_scanner.scanner_row.
  Also use when backtest logic needs to consume scanner decisions.
---

# Building Scanner Rows

## Canonical fields

All fields must come from `market_scanner.scanner_row` — never reimplement elsewhere.

| Field | Type | Values |
|---|---|---|
| `lux_role` | str | Lux context role for current bar |
| `smc_role` | str | SMC context role for current bar |
| `alignment` | str | `bullish_aligned` `bearish_aligned` `mixed` `no_trade` |
| `consistency_score` | int | numeric score combining signal agreement |
| `market_state` | str | `pullback` `range` `extended` |
| `adjusted_alignment` | str | decision-aware alignment after context |
| `action_bucket` | str | `candidate` `watchlist` `avoid` `needs_review` |

## Module responsibility — hard boundary

```
trading_indicators  →  raw Lux/SMC calculations
stock_analyzer      →  lux_role, smc_role per symbol
market_scanner      →  alignment, market_state, action_bucket
```

Never put indicator logic in `market_scanner`.
Never put scanner fields in `stock_analyzer`.

## Eligibility vs decision — never mix

**Eligibility** (before processing):
- CSV exists and has sufficient history
- `market_cap >= threshold`, `avg_volume_20 >= threshold`
- Output: `eligible: bool` + `excluded_reason: str`

**Decision** (after eligibility passes):
- `alignment` → `market_state` → `adjusted_alignment` → `action_bucket`
- Must be deterministic and explicit

## Error handling pattern

```python
try:
    row = build_scanner_row(symbol, df)
    results.append(row)
except Exception as e:
    results.append({"symbol": symbol, "eligible": False, "excluded_reason": str(e)})
```

Never crash the full scan for one symbol.

## Backtest reuse rule

Live scan and backtest share `build_scanner_row`.
If you change it, both outputs change — this is intentional.
Backtest consumes scanner decisions, never reimplements them.

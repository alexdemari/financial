# Skill: Scanner Patterns

Domain knowledge for working with `market_scanner` and Scanner logic.

---

## Scanner Row — Canonical Fields

The shared row is the source of truth. All fields must come from `market_scanner.scanner_row`.

| Field | Type | Values |
|---|---|---|
| `lux_role` | str | Lux context role for current bar |
| `smc_role` | str | SMC context role for current bar |
| `alignment` | str | `bullish_aligned`, `bearish_aligned`, `mixed`, `no_trade` |
| `consistency_score` | int | numeric score combining signal agreement |
| `market_state` | str | `pullback`, `range`, `extended` |
| `adjusted_alignment` | str | decision-aware alignment after context |
| `action_bucket` | str | `candidate`, `watchlist`, `avoid`, `needs_review` |

---

## Module Responsibility

```
trading_indicators  →  raw Lux/SMC calculations
stock_analyzer      →  per-symbol signal (lux_role, smc_role)
market_scanner      →  alignment, market_state, action_bucket
```

Never move indicator logic into `market_scanner`. Never move scanner fields into `stock_analyzer`.

---

## Eligibility vs Decision

Two separate layers — never mix them:

**Eligibility (filter before processing):**
- CSV exists and has sufficient history
- `market_cap >= threshold`
- `avg_volume_20 >= threshold`
- Output: boolean + `excluded_reason`

**Decision (rank eligible symbols):**
- `alignment` → `market_state` → `adjusted_alignment` → `action_bucket`
- Must be deterministic and explicit

---

## Error Handling in Scanner

Never crash the full scan for one symbol. Pattern:

```python
try:
    row = build_scanner_row(symbol, df)
    results.append(row)
except Exception as e:
    results.append({"symbol": symbol, "eligible": False, "excluded_reason": str(e)})
```

---

## Backtest Reuse Rule

Live scan and backtest must share the same scanner row logic.
If you change `build_scanner_row`, both live scan and backtest outputs change.
This is intentional — they must stay synchronized.

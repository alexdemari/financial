---
name: validating-backtest
description: >
  Reviews and implements backtest logic for market_scanner signal validation.
  Use when working with market_scanner.backtest, backtest_execution, or any
  historical replay of scanner decisions. Checks for lookahead bias, metric
  correctness, scanner row reuse, and forward return calculation.
---

# Validating Backtest Logic

## What this backtest does

- Replays Scanner V3 decisions bar by bar over historical OHLC
- Computes forward directional metrics (did price go up/down after signal?)
- Validates signal quality — NOT options PnL, NOT execution simulation

## Hard rules

1. **No lookahead bias** — decisions at bar N use only data available at bar N
2. **Reuse scanner row** — consume `market_scanner.scanner_row`, never reimplement
3. **Forward returns** — measured from bar N+1, never including bar N close
4. **No execution modeling** — no commissions, slippage, fill logic
5. **No options PnL** — directional validation only

## Review checklist

- Bar iteration is chronological — no future bars leak into past decisions
- `action_bucket` values consumed correctly: `candidate` `watchlist` `avoid` `needs_review`
- Forward return windows clearly defined and consistent
- Edge cases handled: < min_bars, no signals, all-avoid universe
- Output schema matches `market_scanner.backtest` expectations

## Output format for reviews

```
LOOKAHEAD RISK:
- <any potential future data leak>

LOGIC ERRORS:
- <wrong bar reference or metric calculation>

SCHEMA ISSUES:
- <missing or misnamed output columns>

SAFE:
- <confirmed correct sections>
```

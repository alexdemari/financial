# Market Scanner Decision Layer

## Purpose

This document describes the decision layer used by `market_scanner`.

Its job is not just to show model outputs. Its job is to answer:

**"Is this asset actionable now?"**

---

## Decision Flow

```text
raw Lux + SMC outputs
  ->
alignment
  ->
market_state
  ->
adjusted_alignment
  ->
action_bucket
```

---

## `market_state`

`market_state` describes the current structural context.

Current values:

- `early_trend`
- `pullback`
- `extended`
- `exhaustion`
- `range`
- `unknown`

This field adds context that plain directional agreement does not capture.

---

## `adjusted_alignment`

`adjusted_alignment` is the current scanner directional decision field.

Examples:

- `bullish_aligned`
- `bearish_aligned`
- `bullish_watchlist`
- `bearish_watchlist`
- `range_watchlist`
- `mixed`
- `no_trade`

Important distinction:

- `alignment` is the raw agreement diagnostic
- `adjusted_alignment` is the decision-aware output after market-state logic

---

## `action_bucket`

`action_bucket` is the scanner's action-oriented classification.

Current values:

- `candidate`
- `watchlist`
- `avoid`
- `needs_review`

Meaning:

- `candidate`
  - actionable setup under current scanner rules
- `watchlist`
  - interesting but not currently strong enough
- `avoid`
  - not actionable
- `needs_review`
  - ambiguous or mixed case that does not fit a clean action class

---

## Why This Layer Exists

Lux and SMC alone are not enough to prioritize assets cleanly.

The current scanner adds:

- context
- actionability
- consistent classification
- shared logic for live scan and historical replay

That shared decision layer is what makes the current backtest meaningful.

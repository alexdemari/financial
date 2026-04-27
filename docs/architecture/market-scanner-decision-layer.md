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
- `bullish_trend`
- `bearish_trend`
- `early_bullish`
- `early_bearish`
- `bullish_watch`
- `bearish_watch`
- `bullish_watchlist`
- `bearish_watchlist`
- `range_watchlist`
- `conflicted`
- `trend_only`
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
  - ambiguous or conflicted case that does not fit a clean action class

---

## Glossary

Use this as the operational meaning of the scanner terms.

### `lux_role`

- `bullish_trigger`
  - Lux already fired a bullish signal
- `bearish_trigger`
  - Lux already fired a bearish signal
- `bullish_trend`
  - Lux trend is bullish, but without a fresh actionable trigger
- `bearish_trend`
  - Lux trend is bearish, but without a fresh actionable trigger
- `neutral`
  - Lux is not adding useful directional information

### `smc_role`

- `bullish_trigger`
  - SMC is giving a bullish early-entry or confluence trigger
- `bearish_trigger`
  - SMC is giving a bearish early-entry or confluence trigger
- `bullish_watch`
  - SMC is hinting bullish reversal potential, but not as a full trigger
- `bearish_watch`
  - SMC is hinting bearish reversal potential, but not as a full trigger
- `neutral`
  - SMC is not contributing a useful directional setup

### `alignment`

- `bullish_aligned`
  - Lux context and SMC trigger point to the same bullish direction
- `bearish_aligned`
  - Lux context and SMC trigger point to the same bearish direction
- `bullish_trend`
  - Lux trend is bullish, but SMC is not contributing a setup
- `bearish_trend`
  - Lux trend is bearish, but SMC is not contributing a setup
- `early_bullish`
  - SMC is turning bullish before Lux has confirmed the move
- `early_bearish`
  - SMC is turning bearish before Lux has confirmed the move
- `bullish_watch`
  - bullish context exists, but not enough for a full aligned setup
- `bearish_watch`
  - bearish context exists, but not enough for a full aligned setup
- `conflicted`
  - Lux and SMC are pointing in opposing directions
- `no_trade`
  - neither model is giving a useful directional read

### `market_state`

- `early_trend`
  - fresh directional move with strong recent momentum
- `pullback`
  - trend context exists and price is in a retracement zone
- `extended`
  - the move is stretched and late
- `exhaustion`
  - the move looks especially overheated or depleted
- `range`
  - price is moving sideways or without clean directional structure
- `unknown`
  - the scanner cannot classify the context confidently

### `adjusted_alignment`

- `bullish_aligned` / `bearish_aligned`
  - actionable directional setup after context adjustment
- `bullish_watchlist` / `bearish_watchlist`
  - directional setup worth monitoring, but not ready
- `range_watchlist`
  - sideways context worth monitoring, but not directional
- `trend_only`
  - Lux trend exists, but SMC is not contributing a setup
- `conflicted`
  - opposing model evidence remains unresolved after context adjustment
- `no_trade`
  - no useful setup after context adjustment

### `action_bucket`

- `candidate`
  - best current setup under scanner rules
- `watchlist`
  - interesting, but not yet actionable
- `avoid`
  - not actionable now
- `needs_review`
  - ambiguous/conflicted case that deserves manual review

---

## Why This Layer Exists

Lux and SMC alone are not enough to prioritize assets cleanly.

The current scanner adds:

- context
- actionability
- consistent classification
- shared logic for live scan and historical replay

That shared decision layer is what makes the current backtest meaningful.

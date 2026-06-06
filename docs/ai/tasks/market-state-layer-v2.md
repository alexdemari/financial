# Task: Implement Scanner V2 Market State Layer

You are working on a local-first Python financial analysis project.

## Context

The project has these architectural boundaries:

- `stock_data_manager`: local OHLC data management
- `trading_indicators`: reusable indicator/model logic
- `stock_analyzer`: single-symbol analysis
- `options_tech_scanner`: multi-symbol scanning, eligibility, ranking and reporting

Do **NOT** break these boundaries.

Scanner V1 already exists inside `options_tech_scanner` and includes:

- `scan.py`
- `universe_loader.py`
- `eligibility.py`
- `ranking.py`
- `report_writer.py`

It loads a local universe, filters by market cap and average volume, runs Lux/SMC through `stock_analyzer`, computes `alignment` and `consistency_score`, writes a full CSV and prints top-N.

The existing BULL_PUT_SPREAD scanner must **NOT** be modified.

---

## Goal

Implement a V2 improvement focused on signal quality.

Add a transparent `market_state` layer to identify whether a symbol is in one of these states:

- `early_trend`
- `pullback`
- `extended`
- `exhaustion`
- `range`
- `unknown`

Then use `market_state` to improve alignment, ranking and decision output.

---

## Why

Current Scanner V1 can detect directional bias, but it does not answer the more important operational question:

> Is this asset actionable now, or is the move already late?

The scanner currently tends to confuse:

- bullish and actionable
- bullish but extended
- bearish and actionable
- bearish but late / near support
- neutral range
- no-trade condition

This causes misleading results.

Example:

- AFRM was classified as `bullish_aligned`
- But visually, the chart showed a strong bullish move already extended near resistance
- The better classification is `bullish_watchlist`, not clean bullish candidate

---

## Validation Examples

Use these examples to guide behavior.

### AFRM

Current scanner output:

- `lux_trend = BULLISH`
- `lux_strength = STRONG`
- `lux_last_event = SELL`
- `lux_days_since_last_event = 2`
- `smc_bias = NEUTRAL`
- `smc_range_position_pct ≈ 78`
- `smc_rsi ≈ 65`
- current `alignment = bullish_aligned`

Chart interpretation:

- trend is bullish
- move is strong
- price is already extended
- price is near resistance
- Stoch/RSI context suggests short-term exhaustion
- this should not be treated as a clean bullish entry

Expected V2 behavior:

- `market_state = extended` or `exhaustion`
- `adjusted_alignment = bullish_watchlist`
- `action_bucket = watchlist`

---

### GILD

Current scanner output:

- `lux_trend = BEARISH`
- `lux_strength = NORMAL`
- `lux_last_event = SELL`
- `lux_days_since_last_event = 3`
- `smc_bias = NEUTRAL`
- `smc_range_position_pct ≈ 9`
- `smc_rsi ≈ 36`
- current `alignment = mixed`

Chart interpretation:

- bearish structure is clear
- price is falling
- current location is near lower range/support
- bearish continuation exists, but the move may be late
- should not be interpreted as bullish or neutral

Expected V2 behavior:

- `market_state = extended` or `exhaustion`
- `adjusted_alignment = bearish_watchlist` preferred if exhaustion is detected
- `adjusted_alignment = bearish_aligned` acceptable if only extended
- `action_bucket = watchlist` preferred when late/near support

---

### NU

Current scanner output:

- `lux_trend = BEARISH`
- `lux_strength = NORMAL`
- `lux_last_event = SELL`
- `lux_days_since_last_event = 0`
- `smc_bias = NEUTRAL`
- `smc_range_position_pct ≈ 23`
- `smc_rsi ≈ 44`
- current `alignment = mixed`

Chart interpretation:

- bearish weak / bearish range
- no clean bullish setup
- recent sell signal
- price below relevant structure
- should not be promoted to bullish candidate

Expected V2 behavior:

- `market_state = range`, `pullback` or `unknown`
- `adjusted_alignment != bullish_aligned`
- `action_bucket = watchlist`, `avoid` or `needs_review`

---

## Implementation Requirements

### 1. Add new module

Create:

```text
src/options_tech_scanner/market_state.py
```

This module must be:

- pure
- local-only
- deterministic
- small
- readable
- rule-based

It must **NOT**:

- call external APIs
- download data
- call `trading_indicators` directly
- duplicate Lux/SMC logic
- modify existing BULL_PUT_SPREAD scanner

It should consume only fields already available in the V1 scanner row/snapshot.

---

## 2. Implement market state classifier

Implement a function similar to:

```python
from collections.abc import Mapping
from typing import Any


def classify_market_state(row: Mapping[str, Any]) -> str:
    ...
```

Allowed return values:

```python
EARLY_TREND = "early_trend"
PULLBACK = "pullback"
EXTENDED = "extended"
EXHAUSTION = "exhaustion"
RANGE = "range"
UNKNOWN = "unknown"
```

Use constants or Enum, depending on existing project style.

Recommended constants:

```python
EARLY_TREND = "early_trend"
PULLBACK = "pullback"
EXTENDED = "extended"
EXHAUSTION = "exhaustion"
RANGE = "range"
UNKNOWN = "unknown"

MARKET_STATES = {
    EARLY_TREND,
    PULLBACK,
    EXTENDED,
    EXHAUSTION,
    RANGE,
    UNKNOWN,
}
```

---

## 3. Inputs available

The current CSV already exposes these fields:

```text
lux_trend
lux_strength
lux_last_event
lux_days_since_last_event
lux_active_event
lux_days_since_active_event
smc_bias
smc_range_position_pct
smc_rsi
smc_last_event
smc_last_event_context
smc_days_since_last_event
alignment
consistency_score
```

The classifier should tolerate missing values and invalid values.

If key numeric fields are missing or cannot be converted to float, return:

```python
UNKNOWN
```

Recommended helper:

```python
def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
```

Recommended helper:

```python
def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
```

---

## 4. Rule order

Order matters.

Apply rules in this order:

1. `exhaustion`
2. `extended`
3. `early_trend`
4. `pullback`
5. `range`
6. `unknown`

Reason:

- exhaustion is a stronger warning than extension
- extension should override early trend
- early trend is more actionable than generic range
- range should be fallback before unknown only when enough context exists

---

## 5. Initial rule set

Keep this intentionally simple and transparent.

### 5.1 Bullish exhaustion

```python
if lux_trend == "BULLISH" and smc_range_position_pct >= 80:
    if smc_rsi >= 65 and lux_last_event == "SELL":
        return EXHAUSTION
```

Interpretation:

- trend is bullish
- price is high in range
- momentum is hot
- latest Lux event warns sell / reversal

This is AFRM-like behavior.

---

### 5.2 Bearish exhaustion

```python
if lux_trend == "BEARISH" and smc_range_position_pct <= 15:
    if smc_rsi <= 35:
        return EXHAUSTION
```

Interpretation:

- trend is bearish
- price is near lower range/support
- momentum is already cold
- continuation may be late

This is GILD-like behavior when deeply oversold.

---

### 5.3 Bullish extension

```python
if lux_trend == "BULLISH" and smc_range_position_pct >= 75:
    if smc_rsi >= 60 or lux_last_event == "SELL":
        return EXTENDED
```

Interpretation:

- bullish trend exists
- but asset is no longer early
- entry should be delayed or treated as watchlist

---

### 5.4 Bearish extension / near support

```python
if lux_trend == "BEARISH" and smc_range_position_pct <= 20:
    if smc_rsi <= 40:
        return EXTENDED
```

Interpretation:

- bearish trend exists
- but price may be near support / lower range
- bearish idea may still exist, but not as clean continuation

---

### 5.5 Early trend

```python
if lux_last_event in {"BUY", "SELL"} and lux_days_since_last_event <= 5:
    if 25 <= smc_range_position_pct <= 70:
        return EARLY_TREND
```

Interpretation:

- recent Lux event
- price is not yet at range extreme
- potentially actionable

---

### 5.6 Pullback in bullish trend

```python
if lux_trend == "BULLISH" and 30 <= smc_range_position_pct <= 60:
    if smc_rsi <= 55:
        return PULLBACK
```

Interpretation:

- bullish trend
- price not extended
- momentum cooled
- possible better entry

---

### 5.7 Pullback in bearish trend

```python
if lux_trend == "BEARISH" and 40 <= smc_range_position_pct <= 70:
    if smc_rsi >= 45:
        return PULLBACK
```

Interpretation:

- bearish trend
- price bounced toward mid/high range
- possible bearish continuation candidate

---

### 5.8 Range

```python
if lux_strength == "NORMAL" and smc_bias == "NEUTRAL":
    if 20 <= smc_range_position_pct <= 80:
        return RANGE
```

Interpretation:

- no strong directional edge
- avoid forcing bullish/bearish classification

---

### 5.9 Fallback

```python
return UNKNOWN
```

---

## 6. Add alignment adjustment

Do not remove the existing V1 alignment logic.

Instead, add a V2 adjustment layer.

Implement a function similar to:

```python
def adjust_alignment_for_market_state(
    alignment: str,
    row: Mapping[str, Any],
    market_state: str,
) -> str:
    ...
```

Keep backward-compatible existing labels:

```text
bullish_aligned
bearish_aligned
mixed
no_trade
```

Add these new labels:

```text
bullish_watchlist
bearish_watchlist
range_watchlist
```

---

## 7. Suggested adjustment rules

### 7.1 Bullish aligned but extended/exhausted

```python
if alignment == "bullish_aligned" and market_state in {"extended", "exhaustion"}:
    return "bullish_watchlist"
```

Reason:

- trend may be bullish
- but not clean entry
- should wait for pullback

---

### 7.2 Bearish mixed with recent sell

```python
if alignment == "mixed":
    if row.get("lux_trend") == "BEARISH" and row.get("lux_last_event") == "SELL":
        if market_state == "exhaustion":
            return "bearish_watchlist"
        return "bearish_aligned"
```

Reason:

- V1 often returns `mixed` because SMC is neutral
- but Lux trend + recent sell gives useful bearish bias
- exhaustion downgrades to watchlist

---

### 7.3 Bearish aligned but exhausted

```python
if alignment == "bearish_aligned" and market_state in {"extended", "exhaustion"}:
    return "bearish_watchlist"
```

Reason:

- bearish move may be real
- but continuation may be late

---

### 7.4 Range

```python
if market_state == "range":
    if alignment in {"bullish_aligned", "bearish_aligned"}:
        return f"{alignment.split('_')[0]}_watchlist"
    return "range_watchlist"
```

Reason:

- avoid overconfidence in ranges
- directional trades require more confirmation

---

### 7.5 Default

```python
return alignment
```

---

## 8. Add action bucket

Add a new field:

```text
action_bucket
```

Allowed values:

```text
candidate
watchlist
avoid
needs_review
```

Implement function similar to:

```python
def classify_action_bucket(
    adjusted_alignment: str,
    market_state: str,
) -> str:
    ...
```

Suggested rules:

```python
if adjusted_alignment in {"bullish_aligned", "bearish_aligned"}:
    if market_state not in {"extended", "exhaustion", "range"}:
        return "candidate"

if adjusted_alignment in {
    "bullish_watchlist",
    "bearish_watchlist",
    "range_watchlist",
}:
    return "watchlist"

if adjusted_alignment == "no_trade":
    return "avoid"

if market_state in {"exhaustion", "unknown"}:
    return "needs_review"

return "needs_review"
```

Important:

- exhaustion should not be a clean candidate
- range should not be a clean directional candidate
- unknown should not be promoted

---

## 9. Integrate with scanner output

Integrate this after V1 fields are computed.

Pseudo-flow:

```python
row["market_state"] = classify_market_state(row)

row["adjusted_alignment"] = adjust_alignment_for_market_state(
    alignment=row["alignment"],
    row=row,
    market_state=row["market_state"],
)

row["action_bucket"] = classify_action_bucket(
    adjusted_alignment=row["adjusted_alignment"],
    market_state=row["market_state"],
)
```

Do not remove:

```text
alignment
consistency_score
```

Keep them for debugging/backward compatibility.

---

## 10. CSV output

Extend full CSV output with these new columns:

```text
market_state
adjusted_alignment
action_bucket
```

Do not remove any existing columns.

Expected CSV should include both old and new fields:

```text
alignment
consistency_score
market_state
adjusted_alignment
action_bucket
```

---

## 11. Terminal output

Update top-N terminal summary to display at least:

```text
symbol
close
lux_trend
lux_strength
smc_range_position_pct
smc_rsi
alignment
adjusted_alignment
market_state
action_bucket
consistency_score
```

The purpose is to make the scanner decision-readable.

Example style:

```text
AFRM | close=62.98 | lux=BULLISH/STRONG | range=78.5 | rsi=64.8 | alignment=bullish_aligned -> bullish_watchlist | state=extended | bucket=watchlist | score=1
```

---

## 12. Tests

Add tests for:

```text
tests/options_tech_scanner/test_market_state.py
```

Also update existing ranking/report tests if they assert exact columns.

Favor behavior tests over implementation-detail tests.

---

## 13. Required test scenarios

### 13.1 AFRM-like case

Input:

```python
row = {
    "lux_trend": "BULLISH",
    "lux_strength": "STRONG",
    "lux_last_event": "SELL",
    "lux_days_since_last_event": 2,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 78,
    "smc_rsi": 65,
    "alignment": "bullish_aligned",
}
```

Expected:

```python
market_state in {"extended", "exhaustion"}
adjusted_alignment == "bullish_watchlist"
action_bucket == "watchlist"
```

---

### 13.2 GILD-like case

Input:

```python
row = {
    "lux_trend": "BEARISH",
    "lux_strength": "NORMAL",
    "lux_last_event": "SELL",
    "lux_days_since_last_event": 3,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 9,
    "smc_rsi": 36,
    "alignment": "mixed",
}
```

Expected:

```python
market_state in {"extended", "exhaustion"}
adjusted_alignment in {"bearish_aligned", "bearish_watchlist"}
action_bucket in {"candidate", "watchlist"}
```

Preferred:

```python
adjusted_alignment == "bearish_watchlist"
action_bucket == "watchlist"
```

---

### 13.3 NU-like case

Input:

```python
row = {
    "lux_trend": "BEARISH",
    "lux_strength": "NORMAL",
    "lux_last_event": "SELL",
    "lux_days_since_last_event": 0,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 23,
    "smc_rsi": 44,
    "alignment": "mixed",
}
```

Expected:

```python
market_state in {"range", "pullback", "unknown"}
adjusted_alignment != "bullish_aligned"
action_bucket in {"watchlist", "avoid", "needs_review"}
```

Do not promote NU to clean bullish candidate.

---

### 13.4 Missing numeric values

Input:

```python
row = {
    "lux_trend": "BULLISH",
    "lux_strength": "STRONG",
    "lux_last_event": "BUY",
    "smc_bias": "NEUTRAL",
    "alignment": "bullish_aligned",
}
```

Expected:

```python
market_state == "unknown"
```

---

### 13.5 Invalid numeric values

Input:

```python
row = {
    "lux_trend": "BULLISH",
    "lux_strength": "STRONG",
    "lux_last_event": "BUY",
    "lux_days_since_last_event": "not-a-number",
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": "bad-value",
    "smc_rsi": "",
    "alignment": "bullish_aligned",
}
```

Expected:

```python
market_state == "unknown"
```

---

### 13.6 Range case

Input:

```python
row = {
    "lux_trend": "BULLISH",
    "lux_strength": "NORMAL",
    "lux_last_event": "HOLD",
    "lux_days_since_last_event": 20,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 50,
    "smc_rsi": 50,
    "alignment": "mixed",
}
```

Expected:

```python
market_state == "range"
adjusted_alignment == "range_watchlist"
action_bucket == "watchlist"
```

---

### 13.7 Clean bullish candidate

Input:

```python
row = {
    "lux_trend": "BULLISH",
    "lux_strength": "STRONG",
    "lux_last_event": "BUY",
    "lux_days_since_last_event": 3,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 55,
    "smc_rsi": 52,
    "alignment": "bullish_aligned",
}
```

Expected:

```python
market_state in {"early_trend", "pullback"}
adjusted_alignment == "bullish_aligned"
action_bucket == "candidate"
```

---

### 13.8 Clean bearish candidate

Input:

```python
row = {
    "lux_trend": "BEARISH",
    "lux_strength": "STRONG",
    "lux_last_event": "SELL",
    "lux_days_since_last_event": 2,
    "smc_bias": "NEUTRAL",
    "smc_range_position_pct": 55,
    "smc_rsi": 48,
    "alignment": "bearish_aligned",
}
```

Expected:

```python
market_state in {"early_trend", "pullback"}
adjusted_alignment == "bearish_aligned"
action_bucket == "candidate"
```

---

## 14. Acceptance criteria

Run:

```bash
pytest tests/options_tech_scanner
```

If applicable, also run:

```bash
pytest tests/stock_analyzer
```

Manual smoke check should produce CSV with new columns:

```text
market_state
adjusted_alignment
action_bucket
```

Expected qualitative behavior:

- AFRM should no longer appear as a clean bullish candidate.
- GILD should be recognized as bearish-biased but late/near support.
- NU should not be promoted to bullish.
- Existing V1 columns remain available.
- Existing BULL_PUT_SPREAD scanner remains untouched.

---

## 15. Design constraints

Do **NOT** introduce:

- network calls
- async
- queues
- Redis
- databases
- event-driven architecture
- distributed processing
- major refactors

Do **NOT**:

- modify `trading_indicators`
- duplicate Lux/SMC logic
- modify existing BULL_PUT_SPREAD scanner
- change public behavior of unrelated CLIs

Keep the implementation:

- local-first
- synchronous
- file-based
- CLI-driven
- deterministic
- easy to test
- easy to reason about

---

## 16. Important architectural principle

The scanner should not answer only:

> Is the asset bullish or bearish?

It should answer:

> Is the asset bullish/bearish and actionable now?

That is the purpose of this V2.

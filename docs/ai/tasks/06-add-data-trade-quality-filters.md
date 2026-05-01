# Task: Add Data & Trade Quality Filters to Execution Backtest

**Status:** Completed

## Context

The execution backtest is now implemented and producing comparison results across exit rules.

Recent analysis shows:

- alignment_break is robust across regimes
- opposite_signal bullish has strong returns but higher risk
- short side is fragile outside alignment_break

However, results are still being affected by:

- extreme outliers (e.g. -100x trades)
- low-quality symbols (low price, low liquidity)
- split / reverse split distortions
- extreme gaps or corrupted data

Example observed issue:

worst_trade = -100% to -200%

This indicates data anomalies or unrealistic execution scenarios.

---

## Goal

Add a data and trade quality filtering layer to the execution backtest to:

- remove unreliable symbols
- prevent extreme outliers from distorting results
- improve robustness of comparison
- make ranking trustworthy for decision-making

---

## Important Principle

Better to remove bad data than optimize around it.

This task improves data quality, not strategy logic.

---

## Scope

Modify only:

- src/market_scanner/backtest_execution.py
- src/market_scanner/trades.py (if needed)

Do NOT modify:

- market_scanner/backtest.py
- market_scanner/scan.py
- trading_indicators
- stock_analyzer

---

## Filters to Implement

### 1. Minimum Price Filter

Reject trades where entry price is too low.

CLI:

--min-price

Default:

5.0

Rule:

if entry_price < min_price:
    skip trade

---

### 2. Minimum Dollar Volume Filter

Avoid illiquid assets.

CLI:

--min-dollar-volume

Default:

1000000

Definition:

dollar_volume = close * volume

Rule:

if dollar_volume < min_dollar_volume:
    skip trade

Use value at entry date.

---

### 3. Extreme Return Cap (Analysis Only)

Do NOT remove trades — cap returns for summary metrics.

CLI:

--max-return-cap

Default:

5.0  (500%)

Apply only for:

- summary metrics
- comparison ranking

Do NOT modify:

- raw_return stored in trades CSV

---

### 4. Gap / Anomaly Filter

Detect unrealistic price jumps.

Rule:

gap = abs(open_t / close_t_minus_1 - 1)

CLI:

--max-gap

Default:

0.5  (50%)

If exceeded:

skip trade

---

### 5. Split / Reverse Split Detection (Simple Heuristic)

Detect extreme OHLC ratio:

high_low_ratio = high / low

If:

high_low_ratio > 5.0

Then:

mark as anomaly → skip trade

---

### 6. Worst Trade Guard (Optional)

CLI:

--max-loss

Default:

-1.0  (-100%)

Rule:

if raw_return < max_loss:
    clamp for metrics only

---

## Filtering Behavior

Apply filters:

- at trade entry (price, volume)
- during trade (gap detection)
- during summary (return cap)

Do NOT:

- silently alter raw data
- delete trades without logging

---

## Logging

Add counters:

- skipped_low_price
- skipped_low_volume
- skipped_gap
- skipped_anomaly

Print summary:

FILTER SUMMARY

low_price: X
low_volume: X
gap_anomaly: X
extreme_ratio: X

---

## CLI Additions

Add:

--min-price
--min-dollar-volume
--max-return-cap
--max-gap
--max-loss

All optional with defaults.

---

## Output Changes

### Trades CSV

Add columns:

- is_filtered
- filter_reason

---

### Summary CSV

Use capped_directional_return for:

- expectancy
- avg_return
- profit_factor

Raw return remains unchanged in trades CSV.

---

## Validation

Manual checks:

Run with:

--exit-rule all
--min-trades 20

Compare:

- before filters
- after filters

Expected:

- fewer extreme values
- more stable expectancy
- reduced variance between runs

---

## Tests

Add tests:

1. Low price filter
2. Dollar volume filter
3. Gap detection
4. Return cap behavior
5. No-filter mode (disable all filters)

Example:

--min-price 0
--min-dollar-volume 0
--max-gap 10

Should match previous behavior.

---

## Acceptance Criteria

- No crash with filters enabled
- Backtest results become more stable
- Outliers no longer dominate ranking
- alignment_break remains robust
- opposite_signal still shows edge but with controlled risk
- Tests pass

---

## Relationship with Next Tasks

This task MUST be completed before:

- SQLite layer
- Cache layer
- LLM explainer

Reason:

Bad data + fast system = faster wrong decisions

---

## Final Principle

Garbage in → garbage out.

Clean the data before trusting the strategy.

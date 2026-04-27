# Task: Add Execution Backtest Layer to market_scanner

## Context

The project has been refactored.

The active scanner package is now:

~~~text
src/market_scanner/
~~~

The old package `options_tech_scanner` is no longer the active path for this work.

Current structure:

~~~text
src/market_scanner/
  backtest.py
  eligibility.py
  event_state.py
  market_state.py
  models.py
  pipeline.py
  ranking.py
  report_writer.py
  scan.py
  scanner_row.py
  universe_loader.py
~~~

Current tests:

~~~text
tests/market_scanner/
  test_backtest.py
  test_eligibility.py
  test_market_state.py
  test_ranking.py
  test_scan.py
  test_universe_loader.py
~~~

The current `market_scanner/backtest.py` validates signal quality using fixed horizons, MFE, MAE, directional returns and summary metrics.

That is useful, but it is not an execution backtest.

It answers:

~~~text
Does the signal have predictive edge?
~~~

It does NOT answer:

~~~text
How much of that edge is captured by an entry/exit rule?
~~~

---

## Goal

Add a new execution backtest layer that simulates trades using scanner rows.

This must be separate from the existing signal-quality backtest.

The new execution backtest should answer:

~~~text
Given a candidate signal, which exit rule captures the best risk-adjusted return?
~~~

---

## Architectural Decision

Keep two different backtest types:

### 1. Signal Backtest

Existing file:

~~~text
src/market_scanner/backtest.py
~~~

Purpose:

~~~text
Validate signal edge using fixed horizons.
~~~

Do not remove or replace it.

### 2. Execution Backtest

New file:

~~~text
src/market_scanner/backtest_execution.py
~~~

Purpose:

~~~text
Simulate entries and exits as trades.
~~~

---

## Files to Add

Create:

~~~text
src/market_scanner/exits.py
src/market_scanner/trades.py
src/market_scanner/backtest_execution.py

tests/market_scanner/test_exits.py
tests/market_scanner/test_trades.py
tests/market_scanner/test_backtest_execution.py
~~~

---

## Entry Rule V1

A trade entry occurs only when:

### Bullish Entry

~~~text
action_bucket == "candidate"
adjusted_alignment == "bullish_aligned"
~~~

Result:

~~~text
side = "bullish"
~~~

### Bearish Entry

~~~text
action_bucket == "candidate"
adjusted_alignment == "bearish_aligned"
~~~

Result:

~~~text
side = "bearish"
~~~

Do not enter only because `action_bucket == candidate`.

The side must be explicit.

---

## Trade Model

Create in:

~~~text
src/market_scanner/trades.py
~~~

Minimum model:

~~~python
from dataclasses import dataclass
from typing import Literal

TradeSide = Literal["bullish", "bearish"]

@dataclass(frozen=True)
class Trade:
    symbol: str
    side: TradeSide
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    bars_held: int
    entry_alignment: str
    exit_reason: str
    raw_return: float
    directional_return: float
    mfe: float | None
    mae: float | None
~~~

Directional return:

~~~text
bullish: raw_return
bearish: -raw_return
~~~

---

## Exit Rules

Create in:

~~~text
src/market_scanner/exits.py
~~~

Implement each exit rule separately.

Do NOT combine them into one rule initially.

Reason:

~~~text
Each exit rule is an experiment.
We need to compare them before composing.
~~~

---

## Exit Rule 1: alignment_break

Function:

~~~python
def exit_on_alignment_break(row: dict, side: str) -> bool:
    ...
~~~

Behavior:

### Bullish

Exit when:

~~~text
adjusted_alignment != "bullish_aligned"
~~~

### Bearish

Exit when:

~~~text
adjusted_alignment != "bearish_aligned"
~~~

Rationale:

~~~text
The directional thesis is no longer clean.
~~~

---

## Exit Rule 2: bucket_downgrade

Function:

~~~python
def exit_on_bucket_downgrade(row: dict) -> bool:
    ...
~~~

Behavior:

Exit when:

~~~text
action_bucket in {"watchlist", "avoid", "needs_review"}
~~~

Rationale:

~~~text
The scanner no longer considers the setup actionable.
~~~

---

## Exit Rule 3: late_state

Function:

~~~python
def exit_on_late_state(row: dict) -> bool:
    ...
~~~

Behavior:

Exit when:

~~~text
market_state in {"extended", "exhaustion"}
~~~

Rationale:

~~~text
The move may be late or exhausted.
~~~

---

## Exit Rule 4: opposite_signal

Function:

~~~python
def exit_on_opposite_signal(row: dict, side: str) -> bool:
    ...
~~~

Behavior:

### Bullish trade exits when:

~~~text
adjusted_alignment == "bearish_aligned"
~~~

### Bearish trade exits when:

~~~text
adjusted_alignment == "bullish_aligned"
~~~

Rationale:

~~~text
The scanner now indicates the opposite directional thesis.
~~~

---

## Exit Rule 5: fixed_bars

Function:

~~~python
def exit_after_n_bars(bars_held: int, limit: int) -> bool:
    ...
~~~

Behavior:

Exit when:

~~~text
bars_held >= limit
~~~

Support limits:

~~~text
5
10
20
~~~

---

## Execution Backtest Flow

File:

~~~text
src/market_scanner/backtest_execution.py
~~~

High-level flow:

~~~text
for each symbol:
    build scanner rows over time
    when no position is open:
        check entry rule
    when position is open:
        update MFE / MAE
        check selected exit rule
        if exit:
            close trade
            store trade
~~~

Important:

- one open trade per symbol at a time
- no pyramiding
- no position sizing
- no commissions
- no slippage
- no options PnL yet

This is still a directional execution backtest.

---

## Execution Semantics V1

Use deterministic and conservative execution rules.

### Entry Timing

When an entry condition is detected on bar `i`:

~~~text
enter at the close of bar i
~~~

Use:

~~~text
entry_price = close of bar i
entry_date = timestamp of bar i
~~~

Rationale:

~~~text
This keeps execution aligned with the existing scanner-row workflow,
which evaluates the full state of the current bar.
~~~

### Exit Timing

When an exit condition is detected on bar `i` while a trade is open:

~~~text
exit at the close of bar i
~~~

Use:

~~~text
exit_price = close of bar i
exit_date = timestamp of bar i
~~~

Do not use next-bar execution in V1.

### Same-Bar Priority

If a position is already open on bar `i`:

~~~text
check exit logic first
~~~

If the trade exits on that bar:

~~~text
do not open a new trade for the same symbol on the same bar
~~~

Rationale:

~~~text
One bar should not both close and reopen a position in V1.
This avoids ambiguous sequencing and optimistic trade counts.
~~~

### End Of Dataset

If a trade is still open on the final available bar:

~~~text
force-close it at the final bar close
~~~

Use:

~~~text
exit_reason = "end_of_data"
~~~

Rationale:

~~~text
The summary should reflect realized trade outcomes for the tested sample.
~~~

### Bars Held Definition

Use this convention:

~~~text
entry bar counts as bar 1
~~~

Examples:

~~~text
trade opened and closed on the same bar -> bars_held = 1
trade opened on bar i and closed on bar i+4 -> bars_held = 5
~~~

For fixed-bar exits:

~~~text
bars_5 means exit when bars_held >= 5
bars_10 means exit when bars_held >= 10
bars_20 means exit when bars_held >= 20
~~~

---

## CLI

Add CLI entry point through module execution:

~~~bash
python -m market_scanner.backtest_execution
~~~

Suggested arguments:

~~~text
--universe-file
--data-dir
--ranking-mode snapshot|recent-event
--exit-rule alignment_break|bucket_downgrade|late_state|opposite_signal|bars_5|bars_10|bars_20
--symbols optional comma-separated list
--min-bars
--output-trades
--output-summary
~~~

Example:

~~~bash
PYTHONPATH=src uv run python -m market_scanner.backtest_execution \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --symbols SMR,AAPL,AFRM \
  --ranking-mode recent-event \
  --exit-rule bucket_downgrade \
  --output-trades reports/market_scanner/execution_trades.csv \
  --output-summary reports/market_scanner/execution_summary.csv
~~~

---

## Output: Trades CSV

Default:

~~~text
reports/market_scanner/execution_trades.csv
~~~

Columns:

~~~text
symbol
side
entry_date
entry_price
exit_date
exit_price
bars_held
entry_alignment
exit_reason
raw_return
directional_return
mfe
mae
exit_rule
ranking_mode
~~~

---

## Output: Summary CSV

Default:

~~~text
reports/market_scanner/execution_summary.csv
~~~

Group by:

~~~text
exit_rule
ranking_mode
side
entry_alignment
~~~

Metrics:

~~~text
total_trades
win_rate
loss_rate
avg_return
median_return
avg_directional_return
median_directional_return
avg_mfe
avg_mae
avg_bars_held
expectancy
best_trade
worst_trade
~~~

---

## Terminal Summary

The terminal should be direct and operational.

Example:

~~~text
EXECUTION BACKTEST

Exit rule: bucket_downgrade
Ranking mode: recent-event

BULLISH trades
trades=42 | win_rate=61.9% | loss_rate=38.1%
avg_directional_return=+3.2% | expectancy=+1.1%
avg_bars_held=8.4 | avg_mfe=+6.8% | avg_mae=-2.9%

BEARISH trades
trades=18 | win_rate=55.6% | loss_rate=44.4%
avg_directional_return=+1.4% | expectancy=+0.3%
avg_bars_held=6.1 | avg_mfe=+4.2% | avg_mae=-2.5%
~~~

Use:

~~~text
BULLISH trades
BEARISH trades
~~~

Do NOT use:

~~~text
BUYING strategy
SELLING strategy
~~~

Reason:

This backtest validates directional signal execution, not options strategy PnL.

---

## MFE / MAE Calculation

For bullish trade:

~~~text
MFE = max(high during trade) / entry_price - 1
MAE = min(low during trade) / entry_price - 1
~~~

For bearish trade:

~~~text
MFE = 1 - min(low during trade) / entry_price
MAE = 1 - max(high during trade) / entry_price
~~~

---

## Expectancy

Use directional returns.

~~~text
expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
~~~

Where:

~~~text
avg_win = average positive directional_return
avg_loss = absolute average negative directional_return
~~~

---

## No-Lookahead Rule

Mandatory.

At bar `i`, scanner row must be built only with:

~~~python
df_slice = df.iloc[:i+1]
~~~

Never use future rows to decide entry or exit.

Future rows may only be used after entry to simulate what happened next.

The execution backtest must reuse the same scanner-row decision path as the
signal backtest.

Use shared scanner-row construction from historical slices, conceptually:

~~~python
row = build_scanner_row_from_history(
    symbol=symbol,
    close=entry_close,
    lux_historical=lux_historical,
    smc_historical=smc_historical,
    index=i,
    ranking_mode=ranking_mode,
)
~~~

Do not reimplement Lux logic, SMC logic, alignment logic, market-state logic,
or action-bucket logic inside `backtest_execution.py`.

---

## Important Design Rule

Do not combine exit rules in V1.

Run each separately.

The purpose is to compare:

~~~text
alignment_break
bucket_downgrade
late_state
opposite_signal
bars_5
bars_10
bars_20
~~~

Only after comparison should we consider compound exits like:

~~~text
first_warning
hard_invalidation_only
~~~

---

## Tests

### tests/market_scanner/test_exits.py

Cover:

- bullish alignment break
- bearish alignment break
- bucket downgrade
- late state
- opposite signal
- fixed bars

---

### tests/market_scanner/test_trades.py

Cover:

- bullish raw/directional return
- bearish raw/directional return
- MFE / MAE calculations
- expectancy calculation

---

### tests/market_scanner/test_backtest_execution.py

Cover:

- opens bullish trade on candidate + bullish_aligned
- opens bearish trade on candidate + bearish_aligned
- does not open on watchlist
- does not open on mixed / neutral
- closes on selected exit rule
- one open trade per symbol
- output schema contains required columns

---

## Acceptance Criteria

Run:

~~~bash
pytest tests/market_scanner
~~~

Run lint:

~~~bash
ruff check src/market_scanner tests/market_scanner
~~~

Manual smoke:

~~~bash
PYTHONPATH=src uv run python -m market_scanner.backtest_execution \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --symbols SMR \
  --ranking-mode recent-event \
  --exit-rule bucket_downgrade
~~~

Expected:

- trades CSV generated
- summary CSV generated
- terminal summary shown
- current `market_scanner/backtest.py` remains working
- no behavior change in `market_scanner.scan`

---

## Non-Goals

Do NOT implement yet:

- options PnL
- commissions
- slippage
- position sizing
- portfolio allocation
- pyramiding
- compound exit rules
- optimization engine

---

## Final Principle

~~~text
Signal backtest validates edge.
Execution backtest validates capture.

Keep them separate.
~~~

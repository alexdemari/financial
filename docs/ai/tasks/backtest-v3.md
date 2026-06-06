# Task: Implement Backtest V3 for `options_tech_scanner`

## Context

The project already contains legacy backtesting modules:

- `src/options_tech_scanner/backtest.py`
- `src/options_tech_scanner/events.py`
- `src/options_tech_scanner/metrics.py`
- `src/options_tech_scanner/worker.py`
- `src/stock_analyzer/backtest.py`

However, these modules do **not** support the current Scanner V3 decision layer:

- `market_state`
- `adjusted_alignment`
- `action_bucket`
- `ranking_mode`
- `recent-event` logic
- `snapshot` logic

We need a new V3-specific backtest path focused on **signal quality validation**, not options PnL simulation.

---

## Goal

Implement a backtest engine that answers:

> Do Scanner V3 candidate/watchlist signals actually work?

This is **not** a trading simulator. This is a **signal evaluation framework**.

It should measure whether Scanner V3 classifications have predictive value over fixed forward horizons.

---

## Architecture Principles

### 1. Single Source of Truth

Create or extract a reusable pure function for building the same scanner row used by the live scanner.

Suggested function:

~~~python
def build_scanner_row(
    symbol: str, df_slice: pd.DataFrame, *, ranking_mode: str
) -> dict:
    ...
~~~

This function must:

- reproduce the same Scanner V3 logic used by `scan.py`
- include Lux fields
- include SMC fields
- include `alignment`
- include `consistency_score`
- include `market_state`
- include `adjusted_alignment`
- include `action_bucket`
- be deterministic
- use only data available up to the current bar

Expected future users of this function:

- `scan.py`
- `backtest_v3.py`
- future API/reporting/LLM layers

Do **not** duplicate the V3 decision logic separately inside the backtest.

---

### 2. No Lookahead Bias

This is mandatory.

For each historical bar, the scanner row must be built only from data available up to that date.

Correct:

~~~python
df_slice = df.iloc[: i + 1]
row = build_scanner_row(df_slice, ranking_mode=ranking_mode)
~~~

Incorrect:

~~~python
row = build_scanner_row(df, ranking_mode=ranking_mode)
~~~

Do not allow:

- future rows in indicators
- full-series normalization
- future close/high/low data in signal generation
- forward returns influencing signal classification
- any use of `df.iloc[i + 1:]` before the signal row is finalized

Forward data may only be used **after** the event is generated, and only for evaluation metrics.

---

## File Structure

Create:

~~~text
src/options_tech_scanner/backtest_v3.py
tests/options_tech_scanner/test_backtest_v3.py
~~~

Optionally create helper module if cleaner:

~~~text
src/options_tech_scanner/scanner_row.py
~~~

Use this helper only if it prevents duplication between `scan.py` and `backtest_v3.py`.

---

## Backtest Flow

For each symbol:

1. Load local OHLC dataframe.
2. Sort by date ascending.
3. Validate minimum history.
4. Loop bar-by-bar.
5. Build a V3 scanner row using only historical data up to the current bar.
6. If row is valid, store an event.
7. Compute forward metrics from future bars.

Suggested loop:

~~~python
HORIZONS = [3, 5, 10, 20]
max_horizon = max(HORIZONS)

for i in range(min_bars, len(df) - max_horizon):
    df_slice = df.iloc[: i + 1]
    row = build_scanner_row(symbol, df_slice, ranking_mode=ranking_mode)

    event = build_backtest_event(
        symbol=symbol,
        date=df.iloc[i]["Date"],
        row=row,
        df=df,
        index=i,
        horizons=HORIZONS,
    )
~~~

---

## Ranking Modes

Backtest must support both:

~~~text
snapshot
recent-event
~~~

Recommended CLI option:

~~~bash
--ranking-mode snapshot
--ranking-mode recent-event
~~~

Optionally allow:

~~~bash
--ranking-mode both
~~~

If `both`, generate events for both modes and include `ranking_mode` in the output.

---

## Event Schema

Each event row must include:

~~~python
{
    "symbol": str,
    "date": str,
    "ranking_mode": str,

    "market_state": str,
    "adjusted_alignment": str,
    "action_bucket": str,
    "consistency_score": int,
    "alignment": str,

    "lux_signal": str,
    "lux_options_hint": str,
    "lux_context": str,
    "lux_trend": str,
    "lux_strength": str,
    "lux_last_event": str,
    "lux_days_since_last_event": int,
    "lux_active_event": str,
    "lux_days_since_active_event": int,

    "smc_signal": str,
    "smc_options_hint": str,
    "smc_context": str,
    "smc_bias": str,
    "smc_range_position_pct": float,
    "smc_rsi": float,

    "entry_close": float,
}
~~~

Then add forward evaluation fields per horizon:

~~~text
return_3
return_5
return_10
return_20
mfe_3
mfe_5
mfe_10
mfe_20
mae_3
mae_5
mae_10
mae_20
win_3
win_5
win_10
win_20
~~~

Only rows with a directional thesis should contribute to directional win/loss metrics.

Rules:

- `candidate` and `watchlist` rows are valid evaluation events
- `avoid` and `needs_review` rows may still be exported for diagnostics
- `neutral` / `no_trade` directional rows must not contribute to `win_rate`, `avg_win`, `avg_loss`, or `expectancy`

---

## Forward Return Metrics

Use fixed horizons:

~~~python
HORIZONS = [3, 5, 10, 20]
~~~

For each horizon:

~~~python
future_close = df.iloc[i + horizon]["Close"]
entry_close = df.iloc[i]["Close"]
return_h = (future_close / entry_close) - 1
~~~

---

## Direction-Aware Evaluation

Use `adjusted_alignment` to infer expected direction.

Suggested helper:

~~~python
def infer_direction(adjusted_alignment: str) -> str:
    if adjusted_alignment.startswith("bullish"):
        return "bullish"
    if adjusted_alignment.startswith("bearish"):
        return "bearish"
    return "neutral"
~~~

Initial win rule:

~~~python
WIN_THRESHOLD = 0.01

if direction == "bullish":
    win = return_h > WIN_THRESHOLD
elif direction == "bearish":
    win = return_h < -WIN_THRESHOLD
else:
    win = None
~~~

Use a threshold to reduce noise.

Do not treat tiny positive/negative moves as meaningful wins.

---

## MFE and MAE

For bullish signals:

~~~python
window = df.iloc[i : i + horizon + 1]
mfe = (window["High"].max() / entry_close) - 1
mae = (window["Low"].min() / entry_close) - 1
~~~

For bearish signals:

~~~python
window = df.iloc[i : i + horizon + 1]
mfe = 1 - (window["Low"].min() / entry_close)
mae = 1 - (window["High"].max() / entry_close)
~~~

For neutral signals, either:

- set MFE/MAE to null, or
- compute unsigned movement separately later

For V1, prefer null for neutral.

---

## Aggregations

Generate grouped metrics by:

- `action_bucket`
- `market_state`
- `adjusted_alignment`
- `lux_strength`
- `ranking_mode`
- `horizon`

Recommended group output columns:

~~~text
group_key
action_bucket
market_state
adjusted_alignment
lux_strength
ranking_mode
horizon
count
win_rate
avg_return
median_return
avg_mfe
avg_mae
avg_win
avg_loss
expectancy
~~~

---

## Expectancy

Compute expectancy per group.

Use absolute loss magnitude for `avg_loss`.

Suggested formula:

~~~python
expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
~~~

Where:

- `win_rate` is between 0 and 1
- `avg_win` is average positive direction-adjusted return
- `avg_loss` is absolute value of average negative direction-adjusted return

For bearish signals, convert returns to direction-adjusted returns first:

~~~python
if direction == "bullish":
    directional_return = return_h
elif direction == "bearish":
    directional_return = -return_h
else:
    directional_return = None
~~~

Then:

~~~python
wins = directional_return > WIN_THRESHOLD
losses = directional_return < -WIN_THRESHOLD
~~~

---

## Outputs

Write detailed event-level CSV:

~~~text
reports/options_scanner/backtest_v3_events.csv
~~~

Write summary CSV:

~~~text
reports/options_scanner/backtest_v3_summary.csv
~~~

Print compact terminal summary:

~~~text
candidate | pullback | STRONG | recent-event | h=10
count=42 | win_rate=62.0% | avg_return=3.2% | expectancy=1.1%
~~~

Terminal output should prioritize:

1. `candidate`
2. `watchlist`
3. strongest market states
4. horizons 5, 10, and 20

---

## CLI Design

Add a CLI entrypoint in `backtest_v3.py`.

Suggested command:

~~~bash
python -m options_tech_scanner.backtest_v3 \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --min-bars 120 \
  --output-events reports/options_scanner/backtest_v3_events.csv \
  --output-summary reports/options_scanner/backtest_v3_summary.csv
~~~

Suggested arguments:

~~~text
--universe-file
--data-dir
--ranking-mode
--min-bars
--horizons
--win-threshold
--output-events
--output-summary
--symbols
~~~

Defaults:

~~~text
ranking_mode = recent-event
min_bars = 120
horizons = 3,5,10,20
win_threshold = 0.01
~~~

---

## Tests

Create:

~~~text
tests/options_tech_scanner/test_backtest_v3.py
~~~

### Test 1: Forward returns

Use synthetic OHLC data.

Verify:

- `return_3`
- `return_5`
- direction-adjusted return
- bullish win
- bearish win

### Test 2: MFE and MAE

Use controlled highs/lows.

Verify:

- bullish MFE/MAE
- bearish MFE/MAE

### Test 3: Event schema

Verify generated event includes:

- symbol
- date
- ranking_mode
- market_state
- adjusted_alignment
- action_bucket
- entry_close
- forward metrics

### Test 4: Aggregation

Given fake event rows, verify:

- group count
- win rate
- average return
- median return
- expectancy

### Test 5: Short series

If dataframe length is less than `min_bars + max_horizon`, no events should be generated.

### Test 6: No lookahead guard

Use monkeypatch or a fake `build_scanner_row` to assert that the passed dataframe ends at the current index.

Example:

~~~python
def fake_build_scanner_row(df_slice, *, ranking_mode):
    assert df_slice.index.max() <= current_i
    return valid_row
~~~

The exact test shape can be adapted to project style.

---

## Implementation Strategy

### Step 1

Extract or create reusable scanner row builder.

Preferred:

~~~text
src/options_tech_scanner/scanner_row.py
~~~

Containing:

~~~python
def build_scanner_row(
    symbol: str, df_slice: pd.DataFrame, *, ranking_mode: str
) -> dict:
    ...
~~~

Then make `scan.py` use it.

Keep changes small.

Do not refactor unrelated scanner behavior.
Do not reimplement V3 rules separately inside `backtest_v3.py`.

### Step 2

Implement `backtest_v3.py` with:

- CLI parsing
- universe loading
- OHLC loading
- bar-by-bar loop
- event generation
- metric calculation
- CSV writing

### Step 3

Implement aggregation functions.

Keep them pure and testable.

Suggested functions:

~~~python
def compute_forward_metrics(df: pd.DataFrame, index: int, horizons: list[int], direction: str) -> dict:
    ...

def summarize_events(events: list[dict]) -> list[dict]:
    ...
~~~

### Step 4

Add tests.

### Step 5

Run validation.

---

## Non-Goals

Do NOT:

- simulate options PnL
- include commissions
- include slippage
- optimize parameters
- add parallelism
- add async
- add queues
- add external services
- modify BULL_PUT_SPREAD scanner
- merge with legacy CSP/BPS backtest

---

## Acceptance Criteria

Run:

~~~bash
pytest tests/options_tech_scanner
~~~

If used in project:

~~~bash
ruff check src/options_tech_scanner tests/options_tech_scanner
~~~

Manual smoke:

~~~bash
python -m options_tech_scanner.backtest_v3 \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event
~~~

Expected files:

~~~text
reports/options_scanner/backtest_v3_events.csv
reports/options_scanner/backtest_v3_summary.csv
~~~

Backtest must answer:

- Do candidates outperform watchlist?
- Does pullback outperform early_trend?
- Is STRONG better than NORMAL?
- Does recent-event improve results?
- Is candidate frequency reasonable?
- Are watchlist setups too conservative or correctly filtered?

---

## Success Criteria

The backtest is successful if it provides reliable numbers for:

- signal count
- candidate frequency
- win rate by horizon
- average and median return
- MFE
- MAE
- expectancy
- ranking mode comparison
- bucket comparison

This will allow Scanner V3 rules to be calibrated based on evidence.

---

## Final Principle

First validate signals.

Then build strategies.

Do not simulate options before proving the signal has directional edge.

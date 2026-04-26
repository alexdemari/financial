# Legacy Options Scanner

## Purpose

The legacy options scanner is the older scan and backtest flow implemented
around [main.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/main.py:1)
and the supporting legacy modules in `options_tech_scanner`.

Its focus is:

- bullish pullback setup detection
- `BULL_PUT_SPREAD`-oriented screening
- setup-style filtering and legacy backtest outputs

This is not the current shared scanner architecture used by `scan.py` and
the current backtest module.

---

## Main Files

The legacy flow is centered on:

- [main.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/main.py:1)
- [backtest.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/backtest.py:1)
- [events.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/events.py:1)
- [metrics.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/metrics.py:1)
- [worker.py](/abs/path/C:/Users/alexa/Documents/development/financial/src/options_tech_scanner/worker.py:1)

Related supporting files include:

- `context.py`
- `indicators.py`
- `setups.py`
- `cache_utils.py`

---

## What It Does

The legacy scanner:

- scans daily CSV data
- applies liquidity gates
- applies context and regime filters
- evaluates setup timing
- emits setup-oriented outputs such as `BULL_PUT_SPREAD`
- runs the legacy backtest path tied to that staged setup engine

It is more setup-specific and options-plan-oriented than the current scanner.

---

## Why It Is Considered Legacy

It is considered legacy because the current architecture now has a separate
shared path for:

- per-symbol Lux and SMC analysis
- current scanner row construction
- current scanner decision logic
- current signal-quality backtest

That newer path is:

- [current-options-scanner.md](/abs/path/C:/Users/alexa/Documents/development/financial/docs/architecture/current-options-scanner.md:1)
- [current-options-scanner-decision-layer.md](/abs/path/C:/Users/alexa/Documents/development/financial/docs/architecture/current-options-scanner-decision-layer.md:1)
- [backtest.md](/abs/path/C:/Users/alexa/Documents/development/financial/docs/architecture/backtest.md:1)

---

## Current Position In The System

The legacy scanner still exists in the codebase and remains useful for:

- historical reference
- setup-specific workflows
- understanding the older `BULL_PUT_SPREAD` flow

But it should not be treated as the main architecture for the current scanner
decision system.

---

## Rule Of Thumb

If the workflow depends on:

- `options_tech_scanner.main`
- `BULL_PUT_SPREAD`
- setup-stage filters such as context, price action, and volume confirmation
- legacy backtest modules

then it belongs to the legacy scanner path.

If the workflow depends on:

- `scan.py`
- `scanner_row.py`
- `market_state`
- `adjusted_alignment`
- `action_bucket`
- the current backtest

then it belongs to the current scanner path.

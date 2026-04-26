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

- [market-scanner.md](/abs/path/C:/Users/alexa/Documents/development/financial/docs/architecture/market-scanner.md:1)
- [market-scanner-decision-layer.md](/abs/path/C:/Users/alexa/Documents/development/financial/docs/architecture/market-scanner-decision-layer.md:1)
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

## Legacy Inventory

The remaining files under `options_tech_scanner` now fall into three groups.

### 1. Compatibility Re-exports

These are not the legacy scanner core anymore. They are temporary shims for the
current scanner namespace migration:

- `scan.py`
- `scanner_row.py`
- `market_state.py`
- `eligibility.py`
- `ranking.py`
- `report_writer.py`
- `universe_loader.py`
- `backtest_v3.py`

Recommended destination:

- keep temporarily as compatibility imports
- remove only after old imports and commands are no longer needed

---

### 2. Strategy-Specific Legacy Core

These files are the real legacy scanner core:

- `main.py`
- `setups.py`
- `events.py`
- `backtest.py`
- `metrics.py`
- `worker.py`
- `scorer.py`

What they represent:

- setup-stage filtering
- `BULL_PUT_SPREAD`-oriented logic
- strategy-specific backtesting
- execution-oriented scoring

Recommended destination:

- do not absorb into the `market_scanner` core
- keep as legacy, or move later into a dedicated strategy/execution package

---

### 3. Legacy Support Modules

These are supporting files for the older scanner path:

- `context.py`
- `indicators.py`
- `loader.py`
- `cache_utils.py`
- `regimes.py`
- `structure.py`
- `volatility.py`
- `config.py`

Assessment:

- some parts are generic in appearance
- many are still tightly coupled to the legacy strategy scanner
- some duplicate behavior that belongs more naturally in
  `trading_indicators` or a future execution-layer package

Recommended treatment:

- migrate only after explicit review
- do not move them into `market_scanner` by default

---

### 4. Likely Obsolete Files

These do not look like part of the active architecture:

- `options_analyzer.py`
- `profile_backtest.py`

Recommended treatment:

- keep only if there is still active operational use
- otherwise retire them in a later cleanup pass

---

## Current Reference Status

The repository currently suggests this practical status:

### Actively Used Inside The Legacy Flow

- `main.py`
- `backtest.py`
- `events.py`
- `metrics.py`
- `worker.py`
- `setups.py`
- `context.py`
- `indicators.py`
- `cache_utils.py`
- `loader.py`
- `scorer.py`

These still appear in direct imports used by the legacy scan/backtest path.

### Present But Not Referenced By The Current Repository Flow

- `config.py`
- `regimes.py`
- `structure.py`
- `volatility.py`
- `options_analyzer.py`
- `profile_backtest.py`

This does not prove they are safe to delete immediately, but it does mean they
should be treated as cleanup candidates rather than core dependencies.

---

## Migration Rule

Do not migrate the legacy scanner as a block.

Use this filter instead:

- generic multi-symbol decision logic -> `market_scanner`
- strategy-specific options execution logic -> keep outside the scanner core
- unclear / partially useful support modules -> review case by case

That keeps `market_scanner` clean as a generic decision engine instead of
turning it into an execution-strategy package.

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

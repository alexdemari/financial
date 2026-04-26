# Task: Review and Update Project Documentation

## Status

Completed in substance. Kept as a historical task record.

This task was originally written around:

- `options_tech_scanner`
- `scanner-v3-decision-layer.md`
- `backtest-v3.md`

The project evolved further during execution. The current canonical names are:

- `market_scanner`
- `docs/architecture/market-scanner.md`
- `docs/architecture/market-scanner-decision-layer.md`
- `docs/architecture/backtest.md`

Code is the source of truth. This file records what the documentation update
work was supposed to achieve and how that maps to the current system.

---

## Original Intent

Update documentation to reflect the real system state:

- local-first execution model
- current scanner decision layer
- current backtest pipeline
- clear module boundaries

Preserve the general documentation structure while improving clarity, accuracy,
and completeness.

---

## What Was Actually Delivered

### Architecture Overview

Delivered.

Updated architecture docs now reflect:

- system-wide module overview
- local-first principle
- CLI-driven workflow
- no required distributed or async infrastructure

Canonical files:

- `docs/architecture/overview.md`
- `docs/architecture/components.md`
- `docs/architecture/logical-view.md`

---

### Module Boundaries

Delivered.

Documented boundaries now distinguish:

- `stock_data_manager` -> local data lifecycle
- `trading_indicators` -> low-level indicator logic
- `stock_analyzer` -> single-symbol signal engine
- `market_scanner` -> multi-symbol orchestration and decision layer
- legacy scanner -> remains under `options_tech_scanner`

Canonical file:

- `docs/architecture/module-boundaries.md`

Important rule retained:

```text
market_scanner MUST NOT implement indicator logic
```

---

### Current Scanner Documentation

Delivered, with updated naming.

Instead of the original planned `scanner-v3` naming, the scanner is now
documented as the current `market_scanner`.

Canonical files:

- `docs/architecture/market-scanner.md`
- `docs/architecture/market-scanner-decision-layer.md`
- `docs/architecture/legacy-options-scanner.md`

The documented decision layer includes:

- `market_state`
- `adjusted_alignment`
- `action_bucket`

And the core scanner question remains:

```text
Is this asset actionable now?
```

---

### Scanner Skill Documentation

Delivered.

The scanner skill doc was updated to remove outdated framing and reflect the
current flow:

```text
raw signals -> alignment -> market_state -> adjusted_alignment -> action_bucket
```

Canonical file:

- `docs/ai/skills/build-scanner.md`

---

### Current Backtest Documentation

Delivered, with updated naming.

Instead of `backtest-v3.md`, the canonical file is now:

- `docs/architecture/backtest.md`

The current documented purpose is:

```text
Validate signal quality, not simulate trades
```

The current documented rule is:

```text
No lookahead bias
Only use information available up to the current bar
```

The documented metrics include:

- forward returns
- directional returns
- MFE
- MAE
- success / failure
- expectancy

---

### Naming Cleanup

Delivered in the active architecture docs.

Examples:

- `evend-model.md` -> `event-model.md`
- current scanner docs renamed to `market-scanner*.md`
- active architecture no longer treats `options_tech_scanner` as the current
  canonical scanner package

---

### README and Entry Docs

Delivered.

Updated:

- root `README.md`
- `src/stock_analyzer/README.md`
- `src/market_scanner/README.md`

These now reflect the actual runtime flow:

```text
stock_data_manager -> stock_analyzer -> market_scanner
```

---

## Literal Scope Items That Evolved

Some original file targets changed name during execution because the system
itself was renamed and clarified:

- `options_tech_scanner` -> current scanner became `market_scanner`
- `scanner-v3-decision-layer.md` -> `market-scanner-decision-layer.md`
- `backtest-v3.md` -> `backtest.md`

This is intentional and reflects the current architecture more accurately than
the original task text.

---

## Remaining Literal Gaps

These were part of the original task wording but were not the main focus of the
completed documentation pass:

- dedicated runbooks such as:
  - `docs/runbooks/run-scanner.md`
  - `docs/runbooks/run-backtest-v3.md`
- filling every placeholder/empty doc outside the architecture pass
  - for example `docs/runbooks/local-setup.md` still needs content

These are follow-up documentation tasks, not blockers for understanding the
current architecture.

---

## Acceptance Outcome

Effectively achieved:

- docs reflect current scanner behavior
- current backtest is documented
- local-first constraint is explicit
- old scanner vs current scanner is separated
- module boundaries are documented
- documentation now matches the real codebase much more closely

---

## Final Principle

```text
Code is the source of truth.
Documentation explains the decisions.
```

# Future State

## Purpose

This document describes likely next steps from the current architecture. It is
not a description of implemented behavior.

---

## Stable Foundations

The project already has four useful layers:

1. local data lifecycle
2. single-symbol signal generation
3. Scanner V3 decision logic
4. signal-quality backtesting

The near-term future should strengthen these layers before introducing more
infrastructure.

---

## Near-Term Priorities

### 1. Documentation Alignment

- finish updating architecture docs
- keep module boundaries explicit
- document the current scanner and backtest clearly

### 2. Scanner Architecture Review

- review `market_scanner` package boundaries
- reduce ambiguity between orchestration, ranking, and reporting
- refactor only where responsibilities are currently blurred

### 3. Backtest Usability

- keep improving summary outputs
- maintain decision-oriented reporting
- preserve shared scanner-row logic as the source of truth

### 4. Performance

- continue optimizing scanner/backtest execution when needed
- prefer reusable historical computations over repeated full recomputation

---

## Things That Should Wait

The following are not current priorities:

- cloud services
- distributed job orchestration
- real-time streaming
- portfolio execution infrastructure
- options PnL simulation as the main validation path
- mandatory LLM-driven decisions

---

## LLM Position

If LLM features are introduced, they should remain optional.

Rule:

- LLM may explain or summarize
- LLM should not replace deterministic decision logic

---

## Architectural Direction

The safest future direction is:

- keep data local
- keep signal generation deterministic
- keep scanner and backtest logic shared
- expand evidence and clarity before expanding infrastructure

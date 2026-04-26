# Event Model

## Current State

The current system does NOT implement an event-driven architecture.

Execution is:

- synchronous
- command-driven
- sequential
- local and file-based

---

## Practical Execution Model

Today the workflows are explicit command pipelines, for example:

```text
download data
  ->
analyze one symbol
  ->
scan a universe
  ->
backtest scanner decisions
```

The handoff between these stages is usually:

- local CSV files
- pandas DataFrames
- exported CSV reports

---

## Conceptual Events Only

Although there are natural milestones in the workflow, they are not modeled as
runtime events.

Examples:

- data updated
- single-symbol analysis generated
- scanner row produced
- backtest summary exported

These are conceptual states, not event contracts.

---

## Why This Matters

The architecture should not imply queues, workers, or reactive orchestration
that does not exist.

For the current stage, the project should be documented as:

- local-first
- deterministic
- CLI-driven
- modular, but not event-driven

---

## Future Direction

If event-driven execution is introduced later, it should be treated as a new
architectural phase.

That future phase should wrap the existing modules instead of changing their
core responsibilities.

For now:

- no event bus
- no async workflow engine
- no distributed event contracts

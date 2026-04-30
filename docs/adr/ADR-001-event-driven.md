# ADR-001: Reject Event-Driven Architecture

**Status:** Decided
**Date:** 2026

---

## Context

As the project grew to include a scanner, backtest, and execution layers, there was a natural pull toward event-driven patterns: emitting signals as events, having consumers react, and decoupling modules through a message bus.

This would enable real-time processing and parallel execution of independent workflows.

---

## Decision

**Rejected.** The project remains synchronous, batch-oriented, and CLI-driven.

Reasons:

- The project is local-first and single-user — event-driven infrastructure solves a distributed coordination problem we don't have
- Synchronous flows are explicit, debuggable, and easy to test without mocking brokers
- The scanner and backtest workflows are batch operations, not streaming — there is no benefit to event emission
- Introducing a message bus (even in-process) would add complexity with no current payoff
- The architecture can evolve toward event-driven later if real-time requirements emerge; adding it now would be premature

---

## Consequences

- Module communication stays as direct function calls and shared data structures
- `market_scanner.scanner_row` is the integration point — a plain data structure, not an event
- Tests remain simple: no need to mock brokers, consumers, or queues
- If real-time processing is ever needed, this decision should be revisited with a concrete use case

---

## What NOT to do (derived from this decision)

- Do not introduce `asyncio` event loops
- Do not introduce Redis pub/sub or any message queue
- Do not introduce Kafka, RabbitMQ, or similar
- Do not use callbacks or observer patterns across module boundaries

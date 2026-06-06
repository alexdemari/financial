# ADR-002: Reject Redis and Kafka

**Status:** Decided
**Date:** 2026

---

## Context

Following ADR-001 (rejection of event-driven architecture), this ADR addresses the specific question of Redis and Kafka — both of which were considered as potential caching or queuing layers.

Redis was evaluated as: session cache for scanner results, inter-process state sharing, or pub/sub for signal events.

Kafka was evaluated as: durable event log for scanner decisions, replay-capable audit trail.

---

## Decision

**Both rejected** for the current stage.

### Redis — rejected because:

- The scanner runs as a one-shot CLI batch — there is nothing to cache between runs that isn't already in a CSV
- Inter-process communication is not needed (single process, single user)
- Adding Redis would require a running daemon, connection management, and serialization — all overhead with no current benefit
- CSV outputs already serve as the persistent record of scanner runs

### Kafka — rejected because:

- Kafka solves distributed log consumption at scale — the project has one process and one user
- The backtest already does historical replay from CSV; a Kafka log would duplicate this without adding capability
- Operational complexity (broker, topics, consumer groups) is entirely unjustified

---

## Consequences

- No external services required to run the project (`uv sync --dev` and CSVs are sufficient)
- Scanner results persist as CSV files — simple, inspectable, portable
- If caching of expensive computations becomes necessary, SQLite (local, zero-infrastructure) is the preferred next step before any networked cache
- This decision is tied to ADR-001 — if event-driven architecture is ever adopted, Redis/Kafka should be re-evaluated in that context

---

## What NOT to do (derived from this decision)

- Do not add `redis-py` or any Redis client to the project
- Do not introduce any always-on background service requirement
- Do not add Kafka, Pulsar, or similar distributed log infrastructure

# Task: Integrate SMC Model into Stock Analyzer

## Goal

Add `--model smc` following the same pattern as `lux`.

---

## Requirements

- create adapter in:
  - `stock_analyzer/signals/smc.py`

- reuse existing SMC logic from shared code
- do NOT duplicate logic

---

## Behavior

- match lux structure:
  - historical signals
  - current snapshot
  - CLI output

---

## Tests

- verify output columns
- verify CLI integration
- no network

---

## Constraints

- do not refactor analyzer architecture
- do not introduce confluence yet

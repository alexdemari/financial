
---

# 📂 2. Tasks (execução direta)

## 📄 `docs/ai/tasks/stock-analyzer-local-only.md`

```markdown
# Task: Add Local-Only Mode to Stock Analyzer

## Goal

Separate:

- analyze existing local CSV
- update/download then analyze

---

## Requirements

### Behavior

- `--local-only`:
  - read existing CSV
  - do NOT call stock_data_manager
  - fail clearly if CSV does not exist

- default mode:
  - keep current behavior
  - update/download before analyzing

---

## Constraints

- no Redis, no async, no event-driven
- minimal refactor
- keep architecture simple

---

## Implementation Notes

- add CLI flag
- branch execution flow explicitly
- optionally extract:
  - `load_local_data`
  - `update_and_load_data`

---

## Tests

- local-only reads CSV
- local-only fails without CSV
- normal mode unchanged
- no network usage

---

## Documentation

- update README
- add CLI examples

# Task: [Feature Name]

**Status:** Planned | In Progress | Done
**Skill:** adding-features | writing-tests | reviewing-code
**Scope:** `src/<module>/` only

---

## Goal

One sentence: what behavior change is being introduced?

---

## Outcome spec

When done, the following must be true:

1. <observable outcome — what works that didn't before>
2. <what must still work — existing behavior preserved>
3. Tests pass: `uv run pytest tests/<module>`
4. <CLI or API contract if applicable>
5. No changes to <list modules that must not change>

---

## Constraints

- <what not to introduce: async, Redis, external DB, etc.>
- <module boundary: changes isolated to which package>
- <performance or compatibility requirement if any>

---

## Key design (optional)

Only include if the implementation approach is constrained.
Skip if the agent should choose the approach.

```
<minimal design sketch if needed>
```

Files to create/modify:
```
src/<module>/...
tests/<module>/...
```

---

## Verification

```bash
# How to manually confirm the feature works
<command to run>
<expected output>

uv run pytest tests/<module>
```

---

## Known limitations / follow-up

- <anything intentionally deferred>

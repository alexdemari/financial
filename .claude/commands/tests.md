# /tests

Generate and run tests for a module.

Usage: `/tests $ARGUMENTS` (e.g., `/tests stock_analyzer lux model`)

---

Use `CLAUDE.md` and `.claude/agents/test-writer.md`.

Step 1: Inspect the current test coverage for the specified module.
Summarize what is covered and what is NOT covered.

Step 2: Propose new tests for uncovered behavior, edge cases, and failure paths.
No network. Use in-memory DataFrames. Follow `.claude/skills/test-conventions.md`.

Step 3: Implement the tests.

At the end, run:
```bash
uv run pytest tests/<module> -v
```
And show the result.

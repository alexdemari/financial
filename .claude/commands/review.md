# /review

Cold code review of recent changes.

Usage: `/review` or `/review $ARGUMENTS`

---

Use `CLAUDE.md` and `.claude/agents/code-reviewer.md`.

Review the changes in the last commit (or `$ARGUMENTS` if a branch/commit is specified).

Read the diff cold — do not assume context from this session.

Check:
1. Module boundaries (see `docs/architecture/module-boundaries.md`)
2. Test quality (no network, behavior-oriented)
3. Correctness and edge cases
4. Documentation alignment with behavior

Output the structured report: MUST FIX / SHOULD FIX / CONSIDER / SAFE TO KEEP.

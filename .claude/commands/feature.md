# /feature

Start a feature session with controlled scope.

Usage: `/feature $ARGUMENTS` (e.g., `/feature add --local-only flag to stock_analyzer`)

---

Use `CLAUDE.md` and the relevant task file from `docs/ai/tasks/` if one exists.

Step 1: Inspect current behavior of the relevant module.
Summarize: current flow, relevant files, constraints.

Step 2: Propose a minimal implementation plan:
- What changes
- Impacted files (list them explicitly)
- Tests to add
- Documentation impact (README, CLI help, architecture docs)

**Do NOT change code yet. Wait for approval.**

---
description: Plan a multi-feature batch, then dispatch one parallel sub-agent per feature.
allowed-tools: Read, Grep, Glob, Agent, TodoWrite
---

You are running the `/plan-parallel` workflow.

**Step 1 — Plan.** Read the feature list in `$ARGUMENTS` (or, if empty, ask the user once for it). For each feature, produce — *in this order, per project convention*:

1. **Files to be modified** (use the `finder` sub-agent to confirm — never `general-purpose` for lookups).
2. Description of the change in those files.
3. Test strategy: which existing tests cover the affected paths, which new tests are required.
4. Acceptance criteria, including bit-identical output where applicable.

Present the plan in a single message and **stop. Wait for the user to approve.**

**Step 2 — Dispatch (only after approval).** In a *single* assistant turn, spawn one parallel sub-agent per approved feature using the `feature-worker` sub-agent. Each must:

1. Implement the feature on a branch named `feat/<short-slug>` (use `git worktree add ../wt-<slug>` if features touch overlapping files).
2. Run `uv run pytest -x -q` against the affected modules. Retry up to 3 times for flaky-looking failures.
3. Run `just verify-identical` if the change is in `src/backtest/`.
4. Return a structured report: `{ feature, branch, commit_sha, tests_passed, verify_passed, files_changed, notes }`.

**Step 3 — Reconcile.** After all sub-agents return, run the full integration suite (`uv run pytest -q`), then prompt the user with the merge plan: which branches to merge, in what order, conflicts to expect.

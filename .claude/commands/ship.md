---
description: Run the full quality gate and ship — lint, test, verify, docs, commit, push.
allowed-tools: Bash, Read, Edit, Grep, Glob
---

You are running the `/ship` workflow. Execute these steps in order. **Do not ask the user for confirmation between steps.** If any step fails, stop and report the failure with the exact error.

All Python tooling runs through `uv run`.

1. **Status check.** Run `git status --short` and `git diff --stat`. If there are no changes, abort with a clear message.

2. **Lint.** Run `uv run ruff check --fix .`. Report any unresolved issues.

3. **Full test suite.** Run `uv run pytest -x -q` (not just changed-files tests). If a test fails, fix it before continuing — do not commit broken tests.

4. **Bit-identical verification.** If the change touches `src/backtest/`, profiling, or parallelization, run `just verify-identical`. If output diverges and the divergence was not explicitly requested, abort.

5. **Docs sync.** Read `README.md` and the `justfile`. If the change introduced new flags, commands, or behaviors, update them. Do not invent unrelated doc changes.

6. **Commit.** Stage with `git add -A` and commit with a descriptive message: `<type>: <imperative summary>` where type ∈ {feat, fix, refactor, perf, docs, test, chore}. Body explains *why*, not *what*.

7. **Push.** Push to the current branch's upstream with `git push`. If no upstream is set, set it. The settings deny direct pushes to `main`/`master` and force-push — abort if asked to bypass.

8. **Report.** Print a summary: branch, commit hash, files touched, test count, lint warnings remaining. **List the exact test command** the user can re-run to validate (per project convention).

$ARGUMENTS

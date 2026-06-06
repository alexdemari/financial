---
description: Bit-identical output verification against the golden baseline.
allowed-tools: Bash, Read
---

You are running the `/verify` workflow to confirm that a refactor has not changed observable behavior.

**Inputs:** `$ARGUMENTS` may specify a baseline tag/commit. If empty, default to `tests/baselines/golden.parquet` or `main`.

All Python tooling runs through `uv run`.

**Steps:**

1. **Locate baseline.** Look for `tests/baselines/golden.parquet`. If missing, generate from `main`:
   - `git stash`
   - `git checkout main`
   - `just bench-output > tests/baselines/golden.parquet`
   - `git checkout -` and `git stash pop`

2. **Run current code.** Execute `just bench-output > /tmp/candidate.parquet`.

3. **Diff.**
   - Parquet/CSV: `uv run python -c "import pandas as pd; a=pd.read_parquet('tests/baselines/golden.parquet'); b=pd.read_parquet('/tmp/candidate.parquet'); pd.testing.assert_frame_equal(a, b)"`
   - JSON: `diff <(jq -S . tests/baselines/golden.json) <(jq -S . /tmp/candidate.json)`

4. **Report.**
   - If identical: print `✓ bit-identical` and exit 0.
   - If different: print the first 50 lines of diff, the row/column where divergence starts, and exit 1. **Do not** auto-update the baseline unless the user explicitly asks.

5. **Show command.** Per project convention, print the exact command the user can re-run to repeat the check: `just verify-identical`.

6. **Reminder.** If this was a *deliberate* semantic change, instruct the user to run `just update-baseline` after they confirm the new output is correct.

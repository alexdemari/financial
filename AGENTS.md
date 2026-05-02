# Project Conventions (canonical)

This file is the source of truth for any AI coding agent working on this repo (Claude Code, Codex CLI, etc.). Tool-specific extensions live in `CLAUDE.md` (slash commands, sub-agents, hooks). Personal/local overrides live in `CLAUDE.local.md` (gitignored).

## Environment

- Development happens on WSL / Ubuntu (Windows host). All shell commands assume `bash` on WSL.
- Python is managed by `uv`; the venv is `.venv` inside the repo. **Always invoke Python tools via `uv run <cmd>`** (`uv run pytest`, `uv run ruff`, `uv run python -m ...`). Never call `pytest` or `python` bare — they may resolve to a system interpreter.
- Editors: PyCharm / Cursor from Windows side. The agent does not need to interact with the editor; just edit files.

## Planning & Communication

- When proposing a plan, **list the files to be modified first**, then describe changes per file. Don't describe before listing.
- After implementing a change, **show the exact test command** that validates it (e.g. `uv run pytest tests/backtest/test_filters.py -k test_min_price -x -q`).
- Prefer **explicit, descriptive variable names** over brevity (`min_price_threshold` over `mp`).

## Testing

- Always run the full test suite after refactors, especially parallelization or changes to function signatures (analyzers, workers, etc.). Use `uv run pytest -x -q`.
- Verify bit-identical output when optimizing existing code paths. Use the project's `verify-identical` recipe.
- When `workers=1` or any sequential mode exists, preserve the original code path to avoid regressions.
- Prefer `-x -q` flags to fail fast during iteration.

## Code Style (Python)

- Follow `ruff` defaults. Run `uv run ruff check --fix .` before committing.
- Type hints on all public functions and methods.
- Prefer pure functions; isolate I/O at module boundaries.
- Use `pathlib.Path` over `os.path`.
- Explicit variable names — see Planning section.

## Commit Practices

- Commit messages: imperative mood, conventional-commit-ish prefix: `feat:`, `fix:`, `refactor:`, `perf:`, `docs:`, `test:`, `chore:`.
- Body explains *why*, not *what*. The diff already shows what.
- After completing a feature or refactor, update relevant docs (justfile, README, etc.) and commit/push as a final step unless told otherwise.

## Domain — Backtest Engine

- **Bit-identical output is a hard contract** for any refactor that does not explicitly change semantics. If you change semantics deliberately, say so in the commit body.
- Treat the SQLite cache as **write-once-read-many**. Never mutate cached rows in-place; invalidate and rewrite instead.
- Temporal split logic must respect the `embargo` parameter; do not leak future data into training windows.
- Performance work must report before/after timings and confirm bit-identical (or document the deliberate divergence).

## Sub-Agents & Parallelism (general)

- When delegating to parallel sub-agents, dispatch them in a **single batch** (one tool-call turn) so the prefix cache is shared.
- The orchestrator must verify sub-agent work (run tests, read changes) before declaring tasks complete.
- Run integration tests after fan-out completes and before any commit.

## What NOT to do

- Do not re-read large files you've already read in this session unless they may have changed.
- Do not improvise long shell command sequences when a `just` recipe exists for it. If a recipe is missing, propose adding it instead of hardcoding the sequence.
- Do not push directly to `main` without an explicit instruction.
- Do not edit `.venv/`, `bench/history.jsonl`, or `tests/baselines/` unless the task explicitly requires it.

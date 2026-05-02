@AGENTS.md

# Claude Code — extras on top of AGENTS.md

The canonical project conventions are in `AGENTS.md` (shared with Codex). This file adds Claude-Code-specific tooling: slash commands, sub-agents, hook expectations, and cost discipline.

## Tooling map

- **`/ship`** — full quality gate (lint → test → verify → docs → commit → push). Use this instead of orchestrating the steps manually.
- **`/verify`** — bit-identical output check vs `tests/baselines/golden.parquet`.
- **`/bench`** — profile + record latency to `bench/history.jsonl`. Surfaces top hotspots; does not implement optimizations.
- **`/plan-parallel`** — plan a multi-feature batch, then dispatch one sub-agent per feature in a single turn. User approves the plan before fan-out.

## Sub-agents

- **`finder`** (Haiku) — for "where is X defined / which files reference Y". ~10× cheaper than `general-purpose`. Always prefer `finder` over `general-purpose` for pure lookups.
- **`feature-worker`** (Sonnet) — owns one feature end-to-end on a worktree. Used by `/plan-parallel`.
- **`general-purpose`** — only for genuinely multi-step reasoning that doesn't fit `finder` or `feature-worker`.

## Permissions & hooks (configured in `.claude/settings.json`)

- Common shell commands (`uv run pytest`, `uv run ruff`, `git status/diff/add/commit/push`, `just *`, `rg`, `grep`) are pre-approved. Sub-agents inherit these — do not ask the user for confirmation on them.
- A `PostToolUse` hook auto-runs `uv run ruff check --fix` on edited Python files. Lint errors do not need a separate turn.
- `Stop` hook reminds you to `/compact` if context > 100k or `/clear` if switching tasks.

## Cost & context discipline

- Prefer `Read` over re-running `Bash` to inspect state already in context.
- For verification, use `/verify`, `/ship`, or `/bench` instead of improvising shell sequences.
- Use `finder` for code lookups — never `general-purpose` for "where is X".
- When a session crosses ~100k tokens of context mid-task, run `/compact`. When switching to an unrelated feature, run `/clear`.
- Spawn parallel sub-agents in a single tool-call batch to share the prefix cache.

## When the user says "ship it"

Equivalent to `/ship`. Do not ask which steps to run.

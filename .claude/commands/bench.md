---
description: Profile the backtest engine and report top hotspots and latency metrics.
allowed-tools: Bash, Read, Write
---

You are running the `/bench` workflow to profile current performance.

All Python tooling runs through `uv run`.

**Steps:**

1. **Warm run.** Execute `just bench` once and discard timings (warms caches).

2. **Measured run.** Execute `just bench` and capture wall + CPU time. Append to `bench/history.jsonl`:
   `{"timestamp": ..., "git_sha": ..., "branch": ..., "wall_s": ..., "cpu_s": ..., "peak_mem_mb": ...}`

3. **Profile.** Run `uv run python -m cProfile -o /tmp/bench.prof -m <entry_module>` for the same workload, then summarize the top 15 functions by cumulative time:
   `uv run python -c "import pstats; pstats.Stats('/tmp/bench.prof').sort_stats('cumulative').print_stats(15)"`

4. **Compare.** Read the last 5 entries from `bench/history.jsonl` and report a delta table: `metric | last | now | Δ | Δ%`.

5. **Hotspot summary.** Print the top 3 hotspots and, for each, propose **one** concrete optimization (vectorization, caching, parallelism, algorithmic). **Do not implement them in this command** — the user will pick which to pursue.

6. **Show command.** Print the exact command to re-run the benchmark: `just bench`.

$ARGUMENTS

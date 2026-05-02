"""
src/bench.py — Runner de benchmark para o backtest do market_scanner.

Lê config/bench.yaml, executa backtest_universe medindo wall time, CPU e
memória de pico, e emite métricas em JSON para stdout (--json) ou texto
legível (padrão). O /bench command appende o JSON a bench/history.jsonl.

Uso:
    uv run python -m src.bench --config config/bench.yaml --json
    uv run python -m src.bench --config config/bench.yaml           # human-readable
"""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _peak_mem_mb() -> float:
    """RSS de pico em MB (Linux/WSL via getrusage)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # Linux: ru_maxrss em kB; macOS: em bytes
    if sys.platform == "darwin":
        return usage.ru_maxrss / 1024 / 1024
    return usage.ru_maxrss / 1024


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def run_bench(config_path: str | Path, emit_json: bool = False) -> int:
    # Import tardio para não pagar o custo antes de medir
    from market_scanner.backtest import backtest_universe

    cfg = _load_config(config_path)

    # Garantir que os diretórios de output existem
    output_keys = [
        "output_events",
        "output_detailed_summary",
        "output_decision_summary",
        "output_lux_summary",
        "output_smc_summary",
    ]
    for key in output_keys:
        if cfg.get(key):
            Path(cfg[key]).parent.mkdir(parents=True, exist_ok=True)

    horizons_raw = cfg.get("horizons", "3,5,10,20")
    horizons = [int(h) for h in str(horizons_raw).split(",")]

    symbols_raw = cfg.get("symbols")
    symbols = [s.strip() for s in symbols_raw.split(",")] if symbols_raw else None

    cache_dir_raw = cfg.get("cache_dir")
    cache_dir = Path(cache_dir_raw) if cache_dir_raw else Path("data/cache")

    kwargs = dict(
        universe_file=cfg["universe_file"],
        data_dir=cfg["data_dir"],
        ranking_mode=cfg.get("ranking_mode", "recent-event"),
        min_bars=cfg.get("min_bars", 120),
        horizons=horizons,
        win_threshold=cfg.get("win_threshold", 0.01),
        output_events=cfg.get("output_events", "reports/bench/backtest_events.csv"),
        output_detailed_summary=cfg.get(
            "output_detailed_summary",
            "reports/bench/backtest_detailed_summary.csv",
        ),
        output_decision_summary=cfg.get(
            "output_decision_summary",
            "reports/bench/backtest_decision_summary.csv",
        ),
        output_lux_summary=cfg.get(
            "output_lux_summary",
            "reports/bench/backtest_lux_summary.csv",
        ),
        output_smc_summary=cfg.get(
            "output_smc_summary",
            "reports/bench/backtest_smc_summary.csv",
        ),
        symbols=symbols,
        start_date=cfg.get("start_date"),
        end_date=cfg.get("end_date"),
        max_bars=cfg.get("max_bars"),
        profile=False,
        workers=cfg.get("workers", 1),
        use_cache=cfg.get("use_cache", True),
        cache_dir=cache_dir,
    )

    t0_wall = time.perf_counter()
    t0_cpu = time.process_time()

    backtest_universe(**kwargs)

    wall_s = round(time.perf_counter() - t0_wall, 3)
    cpu_s = round(time.process_time() - t0_cpu, 3)
    peak_mem_mb = round(_peak_mem_mb(), 1)

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "branch": _git_branch(),
        "config": str(config_path),
        "wall_s": wall_s,
        "cpu_s": cpu_s,
        "peak_mem_mb": peak_mem_mb,
    }

    if emit_json:
        print(json.dumps(metrics))
    else:
        print(
            f"bench: wall={wall_s}s  cpu={cpu_s}s  "
            f"mem={peak_mem_mb}MB  sha={metrics['git_sha']}  "
            f"branch={metrics['branch']}"
        )

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark runner para market_scanner.backtest."
    )
    parser.add_argument(
        "--config",
        default="config/bench.yaml",
        help="Caminho para o bench.yaml (default: config/bench.yaml)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emite métricas em JSON para stdout (para bench/history.jsonl)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return run_bench(config_path=args.config, emit_json=args.emit_json)


if __name__ == "__main__":
    sys.exit(main())

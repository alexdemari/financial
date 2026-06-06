"""
Standalone profiling script for market_scanner scan pipeline.

Usage:
    PYTHONPATH=src uv run python scripts/profile_scanner.py

Measures time per phase:
  - CSV loading (iter_symbol_data)
  - build_scanner_row per symbol (Lux + SMC calc + row assembly)
  - sort + CSV output

Prints top-20 functions by cumulative time and saves report to
reports/profiling/scanner_profile_<date>.txt.
"""

import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "stocks" / "1D"
UNIVERSE_FILE = REPO_ROOT / "data" / "scanner_universe_sample.csv"
OUTPUT_DIR = REPO_ROOT / "reports" / "profiling"
OUTPUT_SCAN = REPO_ROOT / "reports" / "profiling" / "_profile_scan_output.csv"

SYMBOLS = ["AAPL", "NVDA", "MSFT", "WFC", "XOM", "GILD", "NKE"]
ANALYSIS_BARS = 260
RANKING_MODE = "recent-event"
TOP_N = 10

sys.path.insert(0, str(REPO_ROOT / "src"))


def _phase(label: str, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    print(f"  {label:<40} {elapsed:.3f}s")
    return result


def run_scan():
    from market_scanner.pipeline import (
        create_analyzers,
        iter_symbol_data,
        load_selected_universe,
    )
    from market_scanner.eligibility import (
        MIN_HISTORY_ROWS,
        evaluate_symbol_eligibility,
    )
    from market_scanner.report_writer import sort_scanner_results, write_csv_report
    from stock_analyzer.analyzer import StockDataAnalyzer

    print("\n=== Phase timings ===")

    universe = _phase(
        "load_selected_universe",
        load_selected_universe,
        UNIVERSE_FILE,
        SYMBOLS,
    )

    analyzers = create_analyzers(StockDataAnalyzer)

    symbol_data_list = _phase(
        "iter_symbol_data (CSV load)",
        iter_symbol_data,
        universe,
        DATA_DIR,
    )

    eligible_count = 0
    rows = []

    t_lux = 0.0
    t_smc = 0.0
    t_row = 0.0

    for sd in symbol_data_list:
        if sd.load_error or sd.df is None:
            continue

        df_slice = sd.df.tail(ANALYSIS_BARS) if ANALYSIS_BARS else sd.df

        eligibility = evaluate_symbol_eligibility(
            market_cap=sd.market_cap,
            df=df_slice,
            min_market_cap=0,
            min_avg_volume_20=0,
            min_avg_dollar_volume_20=0,
            min_history_rows=MIN_HISTORY_ROWS,
        )
        if not eligibility.eligible:
            continue

        eligible_count += 1

        # measure Lux signal generation separately
        t0 = time.perf_counter()
        lux_signal = analyzers.lux_analyzer.generate_signal(sd.symbol, df_slice)
        lux_historical = analyzers.lux_analyzer.generate_historical_signals(
            sd.symbol, df_slice
        )
        t_lux += time.perf_counter() - t0

        # measure SMC signal generation separately
        t0 = time.perf_counter()
        smc_signal = analyzers.smc_analyzer.generate_signal(sd.symbol, df_slice)
        smc_historical = analyzers.smc_analyzer.generate_historical_signals(
            sd.symbol, df_slice
        )
        t_smc += time.perf_counter() - t0

        if lux_signal is None or smc_signal is None:
            continue

        # measure row assembly (event_state + market_state + ranking)
        from market_scanner.scanner_row import _assemble_scanner_row  # type: ignore[attr-defined]

        t0 = time.perf_counter()
        row = _assemble_scanner_row(
            symbol=sd.symbol,
            lux_signal=lux_signal,
            smc_signal=smc_signal,
            lux_historical=lux_historical,
            smc_historical=smc_historical,
            ranking_mode=RANKING_MODE,
            close=eligibility.close,
            avg_volume_20=eligibility.avg_volume_20,
            avg_dollar_volume_20=eligibility.avg_dollar_volume_20,
            market_cap=sd.market_cap,
        )
        t_row += time.perf_counter() - t0
        rows.append(row)

    print(
        f"  {'Lux calc (total, ' + str(eligible_count) + ' symbols)':<40} {t_lux:.3f}s"
    )
    print(
        f"  {'SMC calc (total, ' + str(eligible_count) + ' symbols)':<40} {t_smc:.3f}s"
    )
    print(f"  {'Row assembly (total)':<40} {t_row:.3f}s")
    if eligible_count > 0:
        print(f"  {'Lux per symbol (avg)':<40} {t_lux/eligible_count:.3f}s")
        print(f"  {'SMC per symbol (avg)':<40} {t_smc/eligible_count:.3f}s")

    import pandas as pd

    result_df = pd.DataFrame(rows)

    _phase(
        "sort + write_csv_report",
        lambda: (
            sort_scanner_results(result_df, sort_by="scanner")
            if not result_df.empty
            else result_df,
            write_csv_report(result_df, OUTPUT_SCAN),
        ),
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"scanner_profile_{date_str}.txt"

    pr = cProfile.Profile()
    pr.enable()

    t_total = time.perf_counter()
    run_scan()
    total_elapsed = time.perf_counter() - t_total

    pr.disable()

    print(f"\n  {'TOTAL':<40} {total_elapsed:.3f}s")

    stream = io.StringIO()
    stats = pstats.Stats(pr, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(20)
    profile_text = stream.getvalue()

    print(f"\n=== cProfile top-20 by cumulative time ===\n{profile_text}")

    summary_lines = [
        f"scanner profile — {date_str}",
        f"symbols: {SYMBOLS}",
        f"analysis_bars: {ANALYSIS_BARS}",
        f"ranking_mode: {RANKING_MODE}",
        f"total elapsed: {total_elapsed:.3f}s",
        "",
        profile_text,
    ]
    report_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"Report saved: {report_path}")

    print("\n=== Bottleneck diagnosis ===")
    _diagnose(profile_text, total_elapsed)


def _diagnose(profile_text: str, total: float):
    lines = profile_text.lower()
    indicators = [
        ("load_symbol_csv / csv", "csv"),
        ("lux", "lux"),
        ("smc", "smc"),
        ("build_scanner_row / assemble", "scanner_row"),
        ("write_csv / to_csv", "output"),
    ]
    hits = [label for label, keyword in indicators if keyword in lines]
    if not hits:
        print("  Cannot auto-diagnose — inspect report manually.")
        return
    print(f"  Dominant keywords in top-20: {', '.join(hits)}")
    print("  -> If 'csv' dominates: I/O bound — SQLite or pre-load cache will help.")
    print(
        "  -> If 'lux'/'smc' dominates: CPU bound — parallelisation or calc cache will help."
    )
    print(
        "  -> If 'scanner_row'/'assemble' dominates: event_state logic is bottleneck."
    )


if __name__ == "__main__":
    main()

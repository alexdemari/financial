import os
import pandas as pd

from options_tech_scanner.metrics import summary_by_strategy
from options_tech_scanner.events import detect_setups

from options_tech_scanner.worker import process_symbol_backtest
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed


def _load_benchmark_df(data_dir: str, symbol: str) -> pd.DataFrame | None:
    path = os.path.join(data_dir, f"{symbol}.csv")
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    except Exception:
        return None


def run_backtest(data_dir="data", lookahead=30):
    tasks = []

    for file in os.listdir(data_dir):
        if file.endswith(".csv"):
            symbol = file.replace(".csv", "")
            path = os.path.join(data_dir, file)
            tasks.append((symbol, path, lookahead))

    if not tasks:
        return {}, []

    all_events = []

    with ProcessPoolExecutor(max_workers=os.cpu_count() - 1) as executor:
        futures = [executor.submit(process_symbol_backtest, task) for task in tasks]

        with tqdm(total=len(futures), desc="📊 Backtest técnico") as pbar:
            for future in as_completed(futures):
                events = future.result()
                all_events.extend(events)
                pbar.update(1)

    return summary_by_strategy(all_events), all_events


def run_backtest_mode(
    data_dir="data", lookahead=30, mode="core", include_diagnostics=False
):
    all_events = []
    spy_df = _load_benchmark_df(data_dir, "SPY")
    xlu_df = _load_benchmark_df(data_dir, "XLU")
    diagnostics = {
        "bars_evaluated": 0,
        "pass_above_sma200": 0,
        "pass_ema_cloud_green": 0,
        "pass_rsi_pullback": 0,
        "pass_not_no_trade_zone": 0,
        "pass_near_ema21": 0,
        "pass_price_action": 0,
        "pass_volume": 0,
        "pass_alpha_rotation": 0,
        "final_setups": 0,
        "final_bps": 0,
        "final_csp": 0,
    }

    for file in os.listdir(data_dir):
        if not file.endswith(".csv"):
            continue

        path = os.path.join(data_dir, file)
        df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")

        events = detect_setups(
            df,
            lookahead=lookahead,
            mode=mode,
            spy_df=spy_df,
            xlu_df=xlu_df,
            diagnostics=diagnostics,
        )
        all_events.extend(events)

    if include_diagnostics:
        return all_events, diagnostics

    return all_events

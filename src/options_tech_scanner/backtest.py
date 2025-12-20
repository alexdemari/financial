import os
import pandas as pd

from options_tech_scanner.metrics import summary_by_strategy
from options_tech_scanner.events import detect_setups

from options_tech_scanner.worker import process_symbol_backtest
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

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
        futures = [
            executor.submit(process_symbol_backtest, task)
            for task in tasks
        ]

        with tqdm(total=len(futures), desc="📊 Backtest técnico") as pbar:
            for future in as_completed(futures):
                events = future.result()
                all_events.extend(events)
                pbar.update(1)

    return summary_by_strategy(all_events), all_events

def run_backtest_mode(data_dir="data", lookahead=30, mode="core"):
    all_events = []

    for file in os.listdir(data_dir):
        if not file.endswith(".csv"):
            continue

        path = os.path.join(data_dir, file)
        df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")

        events = detect_setups(
            df,
            lookahead=lookahead,
            mode=mode
        )
        all_events.extend(events)

    return all_events

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from market_scanner.eligibility import load_symbol_csv
from market_scanner.universe_loader import load_universe
from stock_analyzer.analyzer import StockDataAnalyzer


@dataclass
class AnalyzerBundle:
    lux_analyzer: StockDataAnalyzer
    smc_analyzer: StockDataAnalyzer


@dataclass
class SymbolData:
    symbol: str
    market_cap: float | None
    df: pd.DataFrame | None
    load_error: str | None


def create_analyzers(
    analyzer_cls: type[StockDataAnalyzer] = StockDataAnalyzer,
) -> AnalyzerBundle:
    return AnalyzerBundle(
        lux_analyzer=analyzer_cls(signal_model="lux"),
        smc_analyzer=analyzer_cls(signal_model="smc"),
    )


def load_selected_universe(
    universe_file: str | Path,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    universe = load_universe(universe_file)
    if symbols is None:
        return universe

    selected_symbols = {symbol.upper() for symbol in symbols}
    return universe[universe["symbol"].isin(selected_symbols)].reset_index(drop=True)


def iter_symbol_data(
    universe: pd.DataFrame,
    data_dir: str | Path,
    *,
    transform_df: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
) -> list[SymbolData]:
    rows: list[SymbolData] = []
    for entry in universe.itertuples(index=False):
        symbol = str(entry.symbol).upper()
        market_cap = float(entry.market_cap) if pd.notna(entry.market_cap) else None
        try:
            df = load_symbol_csv(data_dir, symbol)
            if transform_df is not None:
                df = transform_df(df)
        except FileNotFoundError:
            rows.append(SymbolData(symbol, market_cap, None, "missing_csv"))
            continue
        except Exception:
            rows.append(SymbolData(symbol, market_cap, None, "load_failed"))
            continue

        rows.append(SymbolData(symbol, market_cap, df, None))
    return rows

import logging
import pickle
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def get_or_compute_historical(
    *,
    analyzer,
    symbol: str,
    df: pd.DataFrame,
    csv_path: Path | None,
    cache_dir: Path | None,
    model_name: str,
) -> pd.DataFrame:
    cache_path = _resolve_cache_path(
        cache_dir=cache_dir, model_name=model_name, symbol=symbol, csv_path=csv_path
    )
    if cache_path is not None:
        result = _try_load(cache_path)
        if result is not None:
            return result

    computed = analyzer.generate_historical_signals(symbol, df)

    if cache_path is not None:
        _try_save(cache_path, computed)

    return computed


class CachedAnalyzer:
    """Wraps a StockDataAnalyzer, caching generate_historical_signals only."""

    def __init__(self, analyzer, *, csv_path: Path, cache_dir: Path, model_name: str):
        self._analyzer = analyzer
        self._csv_path = csv_path
        self._cache_dir = cache_dir
        self._model_name = model_name

    def generate_signal(self, symbol, df):
        return self._analyzer.generate_signal(symbol, df)

    def generate_historical_signals(self, symbol, df):
        return get_or_compute_historical(
            analyzer=self._analyzer,
            symbol=symbol,
            df=df,
            csv_path=self._csv_path,
            cache_dir=self._cache_dir,
            model_name=self._model_name,
        )


def _resolve_cache_path(
    *,
    cache_dir: Path | None,
    model_name: str,
    symbol: str,
    csv_path: Path | None,
) -> Path | None:
    if cache_dir is None or csv_path is None:
        return None
    try:
        key = _cache_key(symbol, csv_path)
        return cache_dir / model_name / f"{key}.pkl"
    except Exception:
        return None


def _cache_key(symbol: str, csv_path: Path) -> str:
    mtime_ns = csv_path.stat().st_mtime_ns
    return f"{symbol}_{mtime_ns:016x}"


def _try_load(cache_path: Path) -> pd.DataFrame | None:
    try:
        with open(cache_path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _try_save(cache_path: Path, df: pd.DataFrame) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.rename(cache_path)  # atomic on Linux
    except Exception as exc:
        logger.debug("Cache write failed for %s: %s", cache_path, exc)

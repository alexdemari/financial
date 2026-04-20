import json
import os
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
from joblib import Memory

CACHE_VERSION = "indicators_v1"
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_CACHE_ROOT = _BASE_DIR / "cache" / "options_scanner" / "indicators"
_SCAN_CACHE_ROOT = _BASE_DIR / "cache" / "options_scanner" / "scan_results"

location = os.path.join(os.path.dirname(__file__), "../../cache/joblib")
memory = Memory(location=location, verbose=0)


def _ensure_cache_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)


def _symbol_paths(symbol: str, cache_dir: Path) -> tuple[Path, Path]:
    safe_symbol = symbol.upper().replace("/", "_")
    data_path = cache_dir / f"{safe_symbol}.pkl"
    meta_path = cache_dir / f"{safe_symbol}.meta.json"
    return data_path, meta_path


def _source_signature(source_path: Path, df: pd.DataFrame) -> dict[str, Any]:
    st = source_path.stat()
    last_date = (
        df.index[-1].isoformat()
        if not df.empty and isinstance(df.index, pd.DatetimeIndex)
        else ""
    )
    return {
        "cache_version": CACHE_VERSION,
        "source_path": str(source_path.resolve()),
        "source_mtime_ns": int(st.st_mtime_ns),
        "source_size": int(st.st_size),
        "rows": int(len(df)),
        "last_date": last_date,
    }


def load_indicator_cache(
    symbol: str, source_path: str, df: pd.DataFrame, cache_dir: str | None = None
) -> pd.DataFrame | None:
    base_dir = Path(cache_dir) if cache_dir else _CACHE_ROOT
    _ensure_cache_dir(base_dir)

    data_path, meta_path = _symbol_paths(symbol, base_dir)
    if not data_path.exists() or not meta_path.exists():
        return None

    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return None

    expected = _source_signature(Path(source_path), df)
    for key in expected:
        if meta.get(key) != expected[key]:
            return None

    try:
        cached = pd.read_pickle(data_path)
    except Exception:
        return None

    if not isinstance(cached, pd.DataFrame) or len(cached) != len(df):
        return None
    if not cached.index.equals(df.index):
        return None

    return cached


def save_indicator_cache(
    symbol: str,
    source_path: str,
    df: pd.DataFrame,
    indicator_df: pd.DataFrame,
    cache_dir: str | None = None,
) -> None:
    base_dir = Path(cache_dir) if cache_dir else _CACHE_ROOT
    _ensure_cache_dir(base_dir)
    data_path, meta_path = _symbol_paths(symbol, base_dir)

    meta = _source_signature(Path(source_path), df)
    indicator_df.to_pickle(data_path)
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _scan_signature(source_path: Path, scan_config: dict[str, Any]) -> dict[str, Any]:
    st = source_path.stat()
    conf = json.dumps(scan_config, sort_keys=True, separators=(",", ":"))
    conf_hash = hashlib.sha1(conf.encode("utf-8")).hexdigest()[:12]
    return {
        "cache_version": "scan_results_v1",
        "source_path": str(source_path.resolve()),
        "source_mtime_ns": int(st.st_mtime_ns),
        "source_size": int(st.st_size),
        "scan_config_hash": conf_hash,
    }


def _scan_paths(
    symbol: str, scan_signature: dict[str, Any], cache_dir: Path
) -> tuple[Path, Path]:
    safe_symbol = symbol.upper().replace("/", "_")
    conf_hash = scan_signature["scan_config_hash"]
    data_path = cache_dir / f"{safe_symbol}.{conf_hash}.scan.pkl"
    meta_path = cache_dir / f"{safe_symbol}.{conf_hash}.scan.meta.json"
    return data_path, meta_path


def load_scan_result_cache(
    symbol: str,
    source_path: str,
    scan_config: dict[str, Any],
    cache_dir: str | None = None,
) -> dict[str, Any] | None:
    base_dir = Path(cache_dir) if cache_dir else _SCAN_CACHE_ROOT
    _ensure_cache_dir(base_dir)

    signature = _scan_signature(Path(source_path), scan_config)
    data_path, meta_path = _scan_paths(symbol, signature, base_dir)
    if not data_path.exists() or not meta_path.exists():
        return None

    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return None

    for key, value in signature.items():
        if meta.get(key) != value:
            return None

    try:
        cached = pd.read_pickle(data_path)
    except Exception:
        return None

    if not isinstance(cached, dict):
        return None

    return cached


def save_scan_result_cache(
    symbol: str,
    source_path: str,
    scan_config: dict[str, Any],
    payload: dict[str, Any],
    cache_dir: str | None = None,
) -> None:
    base_dir = Path(cache_dir) if cache_dir else _SCAN_CACHE_ROOT
    _ensure_cache_dir(base_dir)

    signature = _scan_signature(Path(source_path), scan_config)
    data_path, meta_path = _scan_paths(symbol, signature, base_dir)

    pd.to_pickle(payload, data_path)
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(signature, f, indent=2)

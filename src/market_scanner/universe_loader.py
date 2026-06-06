import json
from pathlib import Path

import pandas as pd


TV_MARKET_CAP_INDEX = 15


def load_universe(path: str | Path) -> pd.DataFrame:
    universe_path = Path(path)
    suffix = universe_path.suffix.lower()

    if suffix == ".json":
        df = _load_json_universe(universe_path)
    elif suffix == ".csv":
        df = pd.read_csv(universe_path)
    else:
        raise ValueError(f"Unsupported universe file format: {universe_path.suffix}")

    return _normalize_universe(df)


def _load_json_universe(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return pd.DataFrame(payload)

    if "data" not in payload:
        raise ValueError("Universe JSON must contain a 'data' array or a list of rows")

    rows: list[dict] = []
    for entry in payload["data"]:
        raw_symbol = entry.get("s", "")
        symbol = raw_symbol.split(":", 1)[-1] if raw_symbol else ""
        values = entry.get("d", [])
        market_cap = (
            values[TV_MARKET_CAP_INDEX] if len(values) > TV_MARKET_CAP_INDEX else None
        )
        rows.append(
            {
                "symbol": symbol,
                "market_cap_basic": market_cap,
            }
        )
    return pd.DataFrame(rows)


def _normalize_universe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(col).strip().lower() for col in normalized.columns]

    if "symbol" not in normalized.columns:
        raise ValueError("Universe file must contain a 'symbol' column")

    market_cap_column = None
    for candidate in ("market_cap", "market_cap_basic"):
        if candidate in normalized.columns:
            market_cap_column = candidate
            break

    if market_cap_column is None:
        raise ValueError(
            "Universe file must contain 'market_cap' or 'market_cap_basic'"
        )

    normalized = normalized.rename(columns={market_cap_column: "market_cap"})
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper().str.strip()
    normalized["market_cap"] = pd.to_numeric(normalized["market_cap"], errors="coerce")

    return (
        normalized[["symbol", "market_cap"]]
        .drop_duplicates("symbol")
        .reset_index(drop=True)
    )

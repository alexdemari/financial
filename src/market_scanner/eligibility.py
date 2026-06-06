from dataclasses import dataclass
from pathlib import Path

import pandas as pd


MIN_HISTORY_ROWS = 200


@dataclass
class EligibilityResult:
    eligible: bool
    excluded_reason: str | None
    avg_volume_20: float | None
    avg_dollar_volume_20: float | None
    close: float | None


def load_symbol_csv(data_dir: str | Path, symbol: str) -> pd.DataFrame:
    csv_path = Path(data_dir) / f"{symbol}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV for {symbol}: {csv_path}")

    df = pd.read_csv(csv_path)
    date_column = _detect_date_column(df)
    df[date_column] = pd.to_datetime(df[date_column], utc=True, errors="coerce")
    df = df.dropna(subset=[date_column]).set_index(date_column).sort_index()
    return df


def evaluate_symbol_eligibility(
    market_cap: float | None,
    df: pd.DataFrame | None,
    min_market_cap: float,
    min_avg_volume_20: float,
    min_avg_dollar_volume_20: float = 0,
    min_history_rows: int = MIN_HISTORY_ROWS,
) -> EligibilityResult:
    if market_cap is None or pd.isna(market_cap) or market_cap < min_market_cap:
        return EligibilityResult(
            eligible=False,
            excluded_reason="market_cap_below_threshold",
            avg_volume_20=None,
            avg_dollar_volume_20=None,
            close=_latest_close(df),
        )

    if df is None:
        return EligibilityResult(
            eligible=False,
            excluded_reason="missing_csv",
            avg_volume_20=None,
            avg_dollar_volume_20=None,
            close=None,
        )

    if len(df) < min_history_rows:
        return EligibilityResult(
            eligible=False,
            excluded_reason="insufficient_history",
            avg_volume_20=None,
            avg_dollar_volume_20=None,
            close=_latest_close(df),
        )

    avg_volume_20 = calculate_avg_volume_20(df)
    avg_dollar_volume_20 = calculate_avg_dollar_volume_20(df)
    if avg_volume_20 is None or avg_volume_20 < min_avg_volume_20:
        return EligibilityResult(
            eligible=False,
            excluded_reason="avg_volume_20_below_threshold",
            avg_volume_20=avg_volume_20,
            avg_dollar_volume_20=avg_dollar_volume_20,
            close=_latest_close(df),
        )

    if min_avg_dollar_volume_20 > 0 and (
        avg_dollar_volume_20 is None or avg_dollar_volume_20 < min_avg_dollar_volume_20
    ):
        return EligibilityResult(
            eligible=False,
            excluded_reason="avg_dollar_volume_20_below_threshold",
            avg_volume_20=avg_volume_20,
            avg_dollar_volume_20=avg_dollar_volume_20,
            close=_latest_close(df),
        )

    return EligibilityResult(
        eligible=True,
        excluded_reason=None,
        avg_volume_20=avg_volume_20,
        avg_dollar_volume_20=avg_dollar_volume_20,
        close=_latest_close(df),
    )


def calculate_avg_volume_20(df: pd.DataFrame) -> float | None:
    volume_column = _detect_column(df, ["volume"])
    if volume_column is None or len(df) < 20:
        return None

    volume = pd.to_numeric(df[volume_column], errors="coerce").tail(20)
    if volume.isna().any():
        return None
    return float(volume.mean())


def calculate_avg_dollar_volume_20(df: pd.DataFrame) -> float | None:
    close_column = _detect_column(df, ["close"])
    volume_column = _detect_column(df, ["volume"])
    if close_column is None or volume_column is None or len(df) < 20:
        return None

    close = pd.to_numeric(df[close_column], errors="coerce").tail(20)
    volume = pd.to_numeric(df[volume_column], errors="coerce").tail(20)
    dollar_volume = close * volume
    if dollar_volume.isna().any():
        return None
    return float(dollar_volume.mean())


def _detect_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered = {str(col).lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def _detect_date_column(df: pd.DataFrame) -> str:
    column = _detect_column(df, ["date", "datetime"])
    if column is None:
        raise ValueError("CSV must contain a date column")
    return column


def _latest_close(df: pd.DataFrame | None) -> float | None:
    if df is None or df.empty:
        return None
    close_column = _detect_column(df, ["close"])
    if close_column is None:
        return None
    close_value = pd.to_numeric(df[close_column], errors="coerce").iloc[-1]
    if pd.isna(close_value):
        return None
    return float(close_value)

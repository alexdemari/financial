from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


DEFAULT_CACHE_DIR = Path("data/dividends")
DEFAULT_TTL = timedelta(hours=24)


class DividendCacheError(ValueError):
    """Raised when a local dividend cache file cannot be parsed safely."""


@dataclass(frozen=True)
class DividendDistribution:
    date: pd.Timestamp
    amount: float


@dataclass(frozen=True)
class DividendData:
    ticker: str
    yahoo_ticker: str
    current_price: float
    trailing_annual_dividends: float
    trailing_dy: float
    distributions: list[DividendDistribution]
    fetched_at: datetime


def fetch_dividend_data(
    ticker: str,
    br: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    local_only: bool = False,
    ttl: timedelta = DEFAULT_TTL,
) -> DividendData:
    cache_path = Path(cache_dir) / f"{ticker.upper()}.csv"
    if _cache_is_fresh(cache_path, ttl) or local_only:
        try:
            return _read_cache(cache_path)
        except DividendCacheError:
            if local_only:
                raise
            cache_path.unlink(missing_ok=True)

    yahoo_ticker = normalize_yahoo_ticker(ticker, br=br)
    fetched_data = _download_dividend_data(ticker.upper(), yahoo_ticker)
    _write_cache(cache_path, fetched_data)
    return fetched_data


def normalize_yahoo_ticker(ticker: str, br: bool = False) -> str:
    normalized_ticker = ticker.upper()
    if br and not normalized_ticker.endswith(".SA"):
        return f"{normalized_ticker}.SA"
    return normalized_ticker


def _cache_is_fresh(cache_path: Path, ttl: timedelta) -> bool:
    if not cache_path.exists():
        return False
    modified_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
    return datetime.now(UTC) - modified_at < ttl


def _download_dividend_data(ticker: str, yahoo_ticker: str) -> DividendData:
    yf_ticker = yf.Ticker(yahoo_ticker)
    fetched_at = datetime.now(UTC)

    dividends = pd.Series(dtype=float)
    raw_dividends = getattr(yf_ticker, "dividends", dividends)
    if raw_dividends is not None:
        dividends = pd.Series(raw_dividends, dtype=float)

    if dividends.empty:
        ttm_dividends = dividends
    else:
        dividend_index = pd.DatetimeIndex(dividends.index)
        dividends.index = dividend_index
        ttm_cutoff = pd.Timestamp(fetched_at - timedelta(days=365))
        if dividend_index.tz is None:
            ttm_cutoff = ttm_cutoff.tz_localize(None)
        else:
            ttm_cutoff = ttm_cutoff.tz_localize(dividend_index.tz)
        ttm_dividends = dividends[dividends.index >= ttm_cutoff]

    current_price = _get_current_price(yf_ticker)
    trailing_annual_dividends = float(ttm_dividends.sum())
    trailing_dy = (
        trailing_annual_dividends / current_price if current_price > 0 else 0.0
    )
    distributions = [
        DividendDistribution(date=pd.Timestamp(date), amount=float(amount))
        for date, amount in dividends.sort_index().items()
    ]

    return DividendData(
        ticker=ticker,
        yahoo_ticker=yahoo_ticker,
        current_price=current_price,
        trailing_annual_dividends=trailing_annual_dividends,
        trailing_dy=trailing_dy,
        distributions=distributions,
        fetched_at=fetched_at,
    )


def _get_current_price(yf_ticker) -> float:
    fast_info = getattr(yf_ticker, "fast_info", None)
    for attribute_name in ("last_price", "lastPrice"):
        value = getattr(fast_info, attribute_name, None)
        if value is not None and pd.notna(value):
            return float(value)

    history = yf_ticker.history(period="5d", interval="1d")
    if history.empty or "Close" not in history.columns:
        return 0.0
    return float(history["Close"].dropna().iloc[-1])


def _write_cache(cache_path: Path, dividend_data: DividendData) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ticker": dividend_data.ticker,
            "yahoo_ticker": dividend_data.yahoo_ticker,
            "fetched_at": dividend_data.fetched_at.isoformat(),
            "current_price": dividend_data.current_price,
            "trailing_annual_dividends": dividend_data.trailing_annual_dividends,
            "trailing_dy": dividend_data.trailing_dy,
            "date": distribution.date.isoformat(),
            "amount": distribution.amount,
        }
        for distribution in dividend_data.distributions
    ]
    if not rows:
        rows.append(
            {
                "ticker": dividend_data.ticker,
                "yahoo_ticker": dividend_data.yahoo_ticker,
                "fetched_at": dividend_data.fetched_at.isoformat(),
                "current_price": dividend_data.current_price,
                "trailing_annual_dividends": dividend_data.trailing_annual_dividends,
                "trailing_dy": dividend_data.trailing_dy,
                "date": "",
                "amount": 0.0,
            }
        )
    pd.DataFrame(rows).to_csv(cache_path, index=False)


def _read_cache(cache_path: Path) -> DividendData:
    if not cache_path.exists():
        raise FileNotFoundError(f"Dividend cache not found: {cache_path}")

    try:
        cache_df = pd.read_csv(cache_path)
        if cache_df.empty:
            raise DividendCacheError(f"Dividend cache is empty: {cache_path}")

        first_row = cache_df.iloc[0]
        distributions = [
            DividendDistribution(
                date=pd.Timestamp(row["date"]),
                amount=float(row["amount"]),
            )
            for _, row in cache_df.iterrows()
            if isinstance(row["date"], str) and row["date"]
        ]
        return DividendData(
            ticker=str(first_row["ticker"]),
            yahoo_ticker=str(first_row["yahoo_ticker"]),
            current_price=float(first_row["current_price"]),
            trailing_annual_dividends=float(first_row["trailing_annual_dividends"]),
            trailing_dy=float(first_row["trailing_dy"]),
            distributions=distributions,
            fetched_at=datetime.fromisoformat(str(first_row["fetched_at"])),
        )
    except DividendCacheError:
        raise
    except (KeyError, TypeError, ValueError, pd.errors.ParserError) as exc:
        raise DividendCacheError(f"Invalid dividend cache {cache_path}: {exc}") from exc

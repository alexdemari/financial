from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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


def calculate_average_annual_dividend(
    ticker: str,
    years: int = 6,
    dividend_data: DividendData | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    br: bool = False,
    local_only: bool = False,
) -> float:
    """
    Calculate mean annual dividends over the last N complete calendar years.

    The current calendar year is excluded because it is incomplete and would
    systematically undercount dividends, producing a price ceiling that is
    too low. For example, if today is June 2026, the calculation uses
    2020-2025 for a 6-year average, not 2026.

    Payments are grouped by calendar year, summed within each year, and then
    averaged across the most recent complete years available. Missing years
    inside the asset's available history count as zero. At least three
    complete calendar years with dividend payments are required to avoid
    pricing from too little history.
    """
    if years <= 0:
        raise ValueError("years must be greater than zero")

    data = dividend_data
    if data is None:
        try:
            data = fetch_dividend_data(
                ticker=ticker,
                br=br,
                cache_dir=cache_dir,
                local_only=True,
            )
        except FileNotFoundError:
            if local_only:
                raise
            data = fetch_dividend_data(ticker=ticker, br=br, cache_dir=cache_dir)

    distributions = [
        distribution
        for distribution in data.distributions
        if distribution.amount > 0 and pd.notna(distribution.date)
    ]
    current_year = date.today().year
    complete_distributions = [
        distribution
        for distribution in distributions
        if distribution.date.year < current_year
    ]
    years_with_payments = {
        distribution.date.year for distribution in complete_distributions
    }
    if len(years_with_payments) < 3:
        raise ValueError(
            f"{ticker.upper()} has insufficient dividend history: "
            f"{len(years_with_payments)} years with payments, minimum is 3"
        )

    last_complete_year = current_year - 1
    first_available_year = min(years_with_payments)
    first_year = max(first_available_year, last_complete_year - years + 1)
    annual_totals = {year: 0.0 for year in range(first_year, last_complete_year + 1)}
    for distribution in complete_distributions:
        distribution_year = distribution.date.year
        if first_year <= distribution_year <= last_complete_year:
            annual_totals[distribution_year] += float(distribution.amount)

    return sum(annual_totals.values()) / len(annual_totals)


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
            ttm_cutoff = (
                ttm_cutoff.tz_convert(None)
                if ttm_cutoff.tzinfo is not None
                else ttm_cutoff
            )
        else:
            ttm_cutoff = (
                ttm_cutoff.tz_convert(dividend_index.tz)
                if ttm_cutoff.tzinfo is not None
                else ttm_cutoff.tz_localize(dividend_index.tz)
            )
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

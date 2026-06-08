from dataclasses import dataclass

from dividend_tracker.dividend_data import (
    DividendData,
    DividendDistribution,
    fetch_dividend_data,
)


@dataclass(frozen=True)
class PriceCeilingResult:
    ticker: str
    price_ceiling: float
    current_dy: float
    trailing_annual_dividends: float
    current_price: float
    margin_pct: float
    min_dy: float = 0.06
    recent_distributions: tuple[DividendDistribution, ...] = ()

    @property
    def is_below_or_equal_ceiling(self) -> bool:
        return self.current_price <= self.price_ceiling


def calculate_price_ceiling(
    ticker: str,
    min_dy: float,
    dividend_data: DividendData | None = None,
    br: bool = False,
    local_only: bool = False,
) -> PriceCeilingResult:
    if min_dy <= 0:
        raise ValueError("min_dy must be greater than zero")

    data = dividend_data or fetch_dividend_data(
        ticker=ticker,
        br=br,
        local_only=local_only,
    )
    price_ceiling = data.trailing_annual_dividends / min_dy
    margin_pct = (
        (price_ceiling - data.current_price) / data.current_price
        if data.current_price > 0
        else 0.0
    )
    return PriceCeilingResult(
        ticker=ticker.upper(),
        price_ceiling=price_ceiling,
        current_dy=data.trailing_dy,
        trailing_annual_dividends=data.trailing_annual_dividends,
        current_price=data.current_price,
        margin_pct=margin_pct,
        min_dy=min_dy,
        recent_distributions=tuple(data.distributions[-4:]),
    )

from dataclasses import dataclass

from dividend_tracker.dividend_data import (
    DividendData,
    DividendDistribution,
    calculate_average_annual_dividend,
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
    ceiling_method: str = "trailing"
    dividend_base: float = 0.0
    dividend_base_label: str = "TTM"
    recent_distributions: tuple[DividendDistribution, ...] = ()

    def __post_init__(self) -> None:
        if self.dividend_base == 0.0 and self.trailing_annual_dividends != 0.0:
            object.__setattr__(
                self,
                "dividend_base",
                self.trailing_annual_dividends,
            )

    @property
    def is_below_or_equal_ceiling(self) -> bool:
        return self.current_price <= self.price_ceiling


def calculate_price_ceiling(
    ticker: str,
    min_dy: float,
    dividend_data: DividendData | None = None,
    br: bool = False,
    local_only: bool = False,
    ceiling_method: str = "trailing",
) -> PriceCeilingResult:
    if min_dy <= 0:
        raise ValueError("min_dy must be greater than zero")
    if ceiling_method not in {"trailing", "average_6y"}:
        raise ValueError("ceiling_method must be trailing or average_6y")

    data = dividend_data or fetch_dividend_data(
        ticker=ticker,
        br=br,
        local_only=local_only,
    )
    if ceiling_method == "average_6y":
        dividend_base = calculate_average_annual_dividend(
            ticker=ticker,
            dividend_data=data,
            br=br,
            local_only=local_only,
        )
        dividend_base_label = "Media 6 anos"
    else:
        dividend_base = data.trailing_annual_dividends
        dividend_base_label = "TTM"

    price_ceiling = dividend_base / min_dy
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
        ceiling_method=ceiling_method,
        dividend_base=dividend_base,
        dividend_base_label=dividend_base_label,
        recent_distributions=tuple(data.distributions[-4:]),
    )

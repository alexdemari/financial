"""Risk calculations for IBKR portfolio reports.

Option delta is an approximate Black-Scholes proxy because live IBKR portfolio
data may not include Greeks without a market data subscription. The proxy uses
fixed 30% implied volatility and a fixed 5% risk-free rate by default.
"""

from __future__ import annotations

import math
from datetime import date

from ibkr_positions.models import AccountSummary, Portfolio, Position

IV_DEFAULT = 0.30
"""Fixed implied volatility assumption for approximate option delta."""

RF_DEFAULT = 0.05
"""Fixed risk-free rate assumption, using Selic as a rough proxy."""


def concentration_risk(positions: list[Position], threshold: float = 0.25) -> list[str]:
    """Return symbols where |market_value| >= threshold fraction of total portfolio value."""
    total = sum(abs(p.market_value) for p in positions)
    if total == 0:
        return []
    return [p.symbol for p in positions if abs(p.market_value) / total > threshold]


def options_expiring_soon(positions: list[Position], days: int = 7) -> list[Position]:
    """Return option positions expiring within `days` calendar days from today."""
    today = date.today()
    result: list[Position] = []
    for position in positions:
        if position.asset_type != "OPT" or position.expiration is None:
            continue
        try:
            exp_date = date.fromisoformat(position.expiration)
            if (exp_date - today).days <= days:
                result.append(position)
        except ValueError:
            continue
    return result


def short_puts_near_assignment(
    positions: list[Position], buffer_pct: float = 0.05
) -> list[Position]:
    """Return short puts where underlying price is within buffer_pct of strike."""
    result: list[Position] = []
    for position in positions:
        if (
            position.asset_type != "OPT"
            or position.option_type != "PUT"
            or position.quantity >= 0
            or position.strike is None
            or position.underlying_price is None
            or position.strike == 0.0
        ):
            continue
        distance = (position.underlying_price - position.strike) / position.strike
        if distance <= buffer_pct:
            result.append(position)
    return result


def covered_calls_itm(positions: list[Position]) -> list[Position]:
    """Return short calls where underlying price exceeds strike."""
    result: list[Position] = []
    for position in positions:
        if (
            position.asset_type != "OPT"
            or position.option_type != "CALL"
            or position.quantity >= 0
            or position.strike is None
            or position.underlying_price is None
        ):
            continue
        if position.underlying_price > position.strike:
            result.append(position)
    return result


def margin_utilization(summary: AccountSummary) -> float:
    """Return initial_margin / net_liquidation."""
    if summary.net_liquidation == 0:
        return 0.0
    return summary.initial_margin / summary.net_liquidation


def cash_coverage(
    summary: AccountSummary, positions: list[Position]
) -> dict[str, float]:
    """Return dict describing cash vs worst-case assignment of all short puts."""
    short_puts = [
        p
        for p in positions
        if p.asset_type == "OPT" and p.option_type == "PUT" and p.quantity < 0
    ]
    # Each standard equity option contract covers 100 shares
    worst_case_cost = sum(
        abs(p.quantity) * (p.strike or 0.0) * 100.0 for p in short_puts
    )
    covered = summary.total_cash >= worst_case_cost
    return {
        "available_cash": summary.total_cash,
        "worst_case_assignment_cost": worst_case_cost,
        "covered": float(covered),
        "shortfall": max(0.0, worst_case_cost - summary.total_cash),
    }


def cash_shortfall_resolution(portfolio: Portfolio) -> list[dict[str, float | str]]:
    """Return ranked short-put close actions that reduce cash assignment shortfall."""
    coverage = cash_coverage(portfolio.summary, portfolio.positions)
    shortfall = coverage["shortfall"]
    if shortfall <= 0.0:
        return []

    short_puts = [
        p
        for p in portfolio.positions
        if p.asset_type == "OPT"
        and p.option_type == "PUT"
        and p.quantity < 0
        and p.strike is not None
    ]
    short_puts_sorted = sorted(short_puts, key=lambda p: p.unrealized_pnl)

    actions: list[dict[str, float | str]] = []
    remaining_shortfall = shortfall
    for position in short_puts_sorted:
        assignment_cost = abs(position.quantity) * position.strike * 100.0
        shortfall_reduction = min(assignment_cost, remaining_shortfall)
        actions.append(
            {
                "action": "CLOSE",
                "symbol": position.symbol,
                "assignment_cost": assignment_cost,
                "unrealized_pnl": position.unrealized_pnl,
                "shortfall_reduction": shortfall_reduction,
            }
        )
        remaining_shortfall -= assignment_cost
        if remaining_shortfall <= 0.0:
            break

    return actions


def delta_proxy(
    position: Position,
    *,
    iv: float = IV_DEFAULT,
    rf: float = RF_DEFAULT,
) -> float:
    """Approximate Black-Scholes delta for one option leg using fixed IV and RF."""
    if (
        position.asset_type != "OPT"
        or position.option_type not in {"CALL", "PUT"}
        or position.expiration is None
        or position.strike is None
        or position.strike <= 0.0
        or position.quantity == 0.0
        or iv <= 0.0
    ):
        return 0.0

    try:
        expiration_date = date.fromisoformat(position.expiration)
    except ValueError:
        return 0.0

    years_to_expiration = (expiration_date - date.today()).days / 365.0
    if years_to_expiration <= 0.0:
        return 0.0

    underlying_price = _underlying_price_for_delta(position)
    if underlying_price <= 0.0:
        return 0.0

    d1 = (
        math.log(underlying_price / position.strike)
        + (rf + 0.5 * iv**2) * years_to_expiration
    ) / (iv * math.sqrt(years_to_expiration))
    normal_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))

    if position.option_type == "CALL":
        return normal_d1
    return normal_d1 - 1.0


def portfolio_net_delta(portfolio: Portfolio) -> float:
    """Return approximate option book delta in share equivalents."""
    total_delta = 0.0
    for position in portfolio.positions:
        if position.asset_type == "OPT":
            total_delta += delta_proxy(position) * position.quantity * 100.0
    return total_delta


def _underlying_price_for_delta(position: Position) -> float:
    if position.underlying_price is not None and position.underlying_price > 0.0:
        return position.underlying_price

    contract_multiplier = abs(position.quantity) * 100.0
    if contract_multiplier <= 0.0:
        return 0.0

    if position.cost_basis > 0.0:
        return position.cost_basis / contract_multiplier
    if position.market_value != 0.0:
        return abs(position.market_value) / contract_multiplier
    return 0.0

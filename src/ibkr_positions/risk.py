from __future__ import annotations

from datetime import date

from ibkr_positions.models import AccountSummary, Position


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

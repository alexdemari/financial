from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from ibkr_positions.models import Portfolio, Position
from ibkr_positions.risk import (
    cash_coverage,
    cash_shortfall_resolution,
    concentration_risk,
    covered_calls_itm,
    margin_utilization,
    options_expiring_soon,
    portfolio_net_delta,
    short_puts_near_assignment,
)


def render_positions_report(
    portfolio: Portfolio,
    generated_at: datetime | None = None,
) -> str:
    report_time = generated_at or datetime.now(UTC)
    date_str = report_time.strftime("%Y-%m-%d %H:%M")

    summary = portfolio.summary
    positions = portfolio.positions
    option_positions = [p for p in positions if p.asset_type == "OPT"]

    margin_util = margin_utilization(summary)
    invested_capital = summary.net_liquidation - summary.total_cash

    lines: list[str] = [
        f"# IBKR Positions Report — {date_str}",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric              | Value     |",
        "|---------------------|-----------|",
        f"| Net Liquidation     | {_fmt_money(summary.net_liquidation)} |",
        f"| Total Cash          | {_fmt_money(summary.total_cash)} |",
        f"| Invested Capital    | {_fmt_money(invested_capital)} |",
        f"| Margin Utilization  | {margin_util:.1%} |",
        f"| Excess Liquidity    | {_fmt_money(summary.excess_liquidity)} |",
        "",
        "## 2. Cash by Currency",
        "",
        "| Currency | Balance   | Settled Cash |",
        "|----------|-----------|--------------|",
    ]
    non_base_cash = [cb for cb in portfolio.cash if cb.currency != "BASE"]
    if non_base_cash:
        for cb in non_base_cash:
            lines.append(
                f"| {cb.currency} | {_fmt_money(cb.balance)} | {_fmt_money(cb.settled_cash)} |"
            )
    else:
        lines.append("| — | — | — |")

    lines += [
        "",
        "## 3. Portfolio Allocation",
        "",
        "| Asset Type | Market Value | % of NLV |",
        "|------------|--------------|----------|",
    ]
    allocation = _compute_allocation(positions, summary.net_liquidation)
    for asset_type, (value, pct) in allocation.items():
        lines.append(f"| {asset_type} | {_fmt_money(value)} | {pct:.1%} |")
    cash_pct = (
        summary.total_cash / summary.net_liquidation if summary.net_liquidation else 0.0
    )
    lines.append(f"| Cash | {_fmt_money(summary.total_cash)} | {cash_pct:.1%} |")

    lines += [
        "",
        "## 4. Consolidated Positions",
        "",
        "| Symbol | Type | Qty | Market Value | Cost Basis | Unrealized PnL | Weight |",
        "|--------|------|-----|--------------|------------|----------------|--------|",
    ]
    if not positions:
        lines.append("| — | — | — | — | — | — | — |")
    else:
        for p in positions:
            weight = (
                abs(p.market_value) / summary.net_liquidation
                if summary.net_liquidation
                else 0.0
            )
            lines.append(
                f"| {p.symbol} | {p.asset_type} | {p.quantity:+.0f} | "
                f"{_fmt_money(p.market_value)} | {_fmt_money(p.cost_basis)} | "
                f"{_fmt_pnl(p.unrealized_pnl)} | {weight:.1%} |"
            )

    lines += [
        "",
        "## 5. Open Options",
        "",
        "| Underlying | Type | Strike | Expiration | Qty | Delta | Market Value |",
        "|------------|------|--------|------------|-----|-------|--------------|",
    ]
    if not option_positions:
        lines.append("| — | — | — | — | — | — | — |")
    else:
        for p in option_positions:
            delta_str = f"{p.delta:.2f}" if p.delta is not None else "N/A"
            lines.append(
                f"| {p.underlying or '—'} | {p.option_type or '—'} | "
                f"{_fmt_money(p.strike or 0.0)} | {p.expiration or '—'} | "
                f"{p.quantity:+.0f} | {delta_str} | {_fmt_money(p.market_value)} |"
            )

    alerts = _build_alerts(portfolio)
    lines += [
        "",
        "## 6. Risk Analysis",
        "",
        "### ⚠ Alerts",
        "",
    ]
    if alerts:
        for alert in alerts:
            lines.append(f"- {alert}")
    else:
        lines.append("_No alerts._")

    lines += [
        "",
        "### Margin",
        "",
        f"- Margin utilization: {margin_util:.1%}",
        f"- Excess liquidity: {_fmt_money(summary.excess_liquidity)}",
        f"- Buying power: {_fmt_money(summary.buying_power)}",
    ]

    coverage = cash_coverage(summary, positions)
    if coverage["worst_case_assignment_cost"] > 0:
        if coverage["covered"]:
            coverage_str = "✓ Covered"
        else:
            coverage_str = f"✗ Shortfall {_fmt_money(coverage['shortfall'])}"
        lines += [
            "",
            "### Cash Coverage (Short Puts)",
            "",
            f"- Worst-case assignment cost: {_fmt_money(coverage['worst_case_assignment_cost'])}",
            f"- Available cash: {_fmt_money(coverage['available_cash'])}",
            f"- Status: {coverage_str}",
        ]

    lines += [
        "",
        "## 7. Enhanced Risk",
        "",
        "### Approximate Net Portfolio Delta",
        "",
    ]
    net_delta = portfolio_net_delta(portfolio)
    lines.append(f"- Net option delta: {net_delta:+.2f} ({_delta_label(net_delta)})")
    lines.append(
        "- Estimate uses fixed 30% IV and 5% risk-free rate when live Greeks are unavailable."
    )

    shortfall_actions = cash_shortfall_resolution(portfolio)
    lines += [
        "",
        "### Cash Shortfall Resolution",
        "",
    ]
    if shortfall_actions:
        for action in shortfall_actions:
            lines.append(
                f"- {action['action']} {action['symbol']}: reduces shortfall by "
                f"{_fmt_money(float(action['shortfall_reduction']))} "
                f"(assignment cost {_fmt_money(float(action['assignment_cost']))}, "
                f"unrealized PnL {_fmt_pnl(float(action['unrealized_pnl']))})"
            )
    elif coverage["worst_case_assignment_cost"] > 0:
        lines.append(
            "- No shortfall action needed; cash covers short-put assignment risk."
        )
    else:
        lines.append("- No short-put assignment cash shortfall.")

    concentration_details = _build_concentration_details(portfolio)
    lines += [
        "",
        "### Concentration Details",
        "",
    ]
    if concentration_details:
        for detail in concentration_details:
            lines.append(
                f"- {detail['symbol']}: {float(detail['weight']):.1%} of NLV. "
                f"Suggested action: {detail['suggested_action']}"
            )
    else:
        lines.append("- No position exceeds the 25% concentration threshold.")

    lines += [
        "",
        "## 8. Actionable Insights",
        "",
    ]
    insights = _build_insights(portfolio, margin_util, coverage)
    if insights:
        for insight in insights:
            lines.append(f"- {insight}")
    else:
        lines.append("_No actionable insights at this time._")

    lines.append("")
    return "\n".join(lines)


def write_positions_report(
    portfolio: Portfolio,
    output_dir: str | Path = "reports/output",
    generated_at: datetime | None = None,
) -> tuple[Path, Path, Path]:
    from ibkr_positions.html_report import write_html_report

    report_time = generated_at or datetime.now(UTC)
    date_str = report_time.strftime("%Y-%m-%d")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    md_path = output / f"ibkr_positions_{date_str}.md"
    csv_path = output / f"ibkr_positions_{date_str}.csv"

    md_content = render_positions_report(portfolio, generated_at=report_time)
    md_path.write_text(md_content, encoding="utf-8")
    _write_positions_csv(
        portfolio,
        csv_path,
    )
    html_path = write_html_report(
        portfolio, output_dir=output, generated_at=report_time
    )

    return md_path, csv_path, html_path


def _write_positions_csv(
    portfolio: Portfolio,
    csv_path: Path,
) -> None:
    positions = portfolio.positions
    net_liquidation = portfolio.summary.net_liquidation
    coverage = cash_coverage(portfolio.summary, positions)
    net_portfolio_delta = portfolio_net_delta(portfolio)
    fieldnames = [
        "symbol",
        "type",
        "qty",
        "market_value",
        "cost_basis",
        "unrealized_pnl",
        "weight",
        "underlying",
        "option_type",
        "strike",
        "expiration",
        "available_cash",
        "cash_shortfall",
        "net_portfolio_delta",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for p in positions:
            weight = abs(p.market_value) / net_liquidation if net_liquidation else 0.0
            writer.writerow(
                {
                    "symbol": p.symbol,
                    "type": p.asset_type,
                    "qty": p.quantity,
                    "market_value": p.market_value,
                    "cost_basis": p.cost_basis,
                    "unrealized_pnl": p.unrealized_pnl,
                    "weight": f"{weight:.4f}",
                    "underlying": p.underlying or "",
                    "option_type": p.option_type or "",
                    "strike": p.strike if p.strike is not None else "",
                    "expiration": p.expiration or "",
                    "available_cash": portfolio.summary.total_cash,
                    "cash_shortfall": coverage["shortfall"],
                    "net_portfolio_delta": net_portfolio_delta,
                }
            )


def _compute_allocation(
    positions: list[Position], net_liquidation: float
) -> dict[str, tuple[float, float]]:
    buckets: dict[str, float] = {}
    for p in positions:
        buckets[p.asset_type] = buckets.get(p.asset_type, 0.0) + p.market_value
    result: dict[str, tuple[float, float]] = {}
    for asset_type in sorted(buckets):
        value = buckets[asset_type]
        pct = value / net_liquidation if net_liquidation else 0.0
        result[asset_type] = (value, pct)
    return result


def _build_alerts(portfolio: Portfolio) -> list[str]:
    alerts: list[str] = []
    positions = portfolio.positions

    for symbol in concentration_risk(positions, threshold=0.25):
        alerts.append(f"Concentration risk: {symbol} exceeds 25% of portfolio value")

    for p in options_expiring_soon(positions, days=7):
        alerts.append(
            f"Option expiring soon: {p.symbol} expires {p.expiration} (qty {p.quantity:+.0f})"
        )

    for p in short_puts_near_assignment(positions):
        alerts.append(
            f"Short put near assignment: {p.symbol} strike {p.strike} "
            f"vs underlying {p.underlying_price:.2f}"
        )

    for p in covered_calls_itm(positions):
        alerts.append(
            f"Covered call ITM: {p.symbol} strike {p.strike} "
            f"vs underlying {p.underlying_price:.2f}"
        )

    margin_util = margin_utilization(portfolio.summary)
    if margin_util > 0.5:
        alerts.append(f"High margin utilization: {margin_util:.1%}")

    return alerts


def _build_insights(
    portfolio: Portfolio,
    margin_util: float,
    coverage: dict[str, float],
) -> list[str]:
    insights: list[str] = []
    positions = portfolio.positions
    option_positions = [p for p in positions if p.asset_type == "OPT"]

    short_opts = [p for p in option_positions if p.quantity < 0]
    if short_opts:
        insights.append(
            f"{len(short_opts)} short option position(s) generating premium income"
        )

    if margin_util < 0.2:
        insights.append("Low margin utilization — significant capacity available")
    elif margin_util > 0.4:
        insights.append("Elevated margin utilization — consider reducing exposure")

    if coverage["worst_case_assignment_cost"] > 0:
        if coverage["covered"]:
            insights.append("Cash fully covers worst-case assignment of all short puts")
        elif coverage["shortfall"] > 0:
            insights.append(
                f"Cash shortfall of {_fmt_money(coverage['shortfall'])} "
                "if all short puts assigned"
            )

    return insights


def _build_concentration_details(portfolio: Portfolio) -> list[dict[str, float | str]]:
    if portfolio.summary.net_liquidation == 0.0:
        return []

    details: list[dict[str, float | str]] = []
    flagged_symbols = concentration_risk(portfolio.positions, threshold=0.25)
    for symbol in flagged_symbols:
        symbol_value = sum(
            abs(position.market_value)
            for position in portfolio.positions
            if position.symbol == symbol
        )
        weight = symbol_value / portfolio.summary.net_liquidation
        details.append(
            {
                "symbol": symbol,
                "weight": weight,
                "suggested_action": "reduce exposure or hedge before adding risk",
            }
        )
    return details


def _delta_label(net_delta: float) -> str:
    if net_delta > 0.10:
        return "bullish"
    if net_delta < -0.10:
        return "bearish"
    return "neutral"


def _fmt_money(value: float) -> str:
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def _fmt_pnl(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}${value:,.2f}"

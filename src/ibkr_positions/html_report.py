from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ibkr_positions.models import Portfolio, Position
from ibkr_positions.risk import (
    cash_coverage,
    concentration_risk,
    covered_calls_itm,
    margin_utilization,
    options_expiring_soon,
    short_puts_near_assignment,
)

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f0f2f5; color: #1a1a2e; font-size: 14px; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; color: #0d1b2a; }
.subtitle { color: #6b7280; font-size: 13px; margin-bottom: 24px; }
h2 { font-size: 15px; font-weight: 600; color: #0d1b2a; margin-bottom: 12px;
     padding-bottom: 6px; border-bottom: 2px solid #e5e7eb; }
.section { background: #fff; border-radius: 8px; padding: 20px;
           margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
         gap: 12px; margin-bottom: 20px; }
.card { background: #fff; border-radius: 8px; padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.card-label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
              color: #6b7280; margin-bottom: 4px; }
.card-value { font-size: 20px; font-weight: 700; color: #0d1b2a; }
.card-value.pos { color: #059669; }
.card-value.neg { color: #dc2626; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f9fafb; text-align: left; padding: 8px 10px; font-weight: 600;
     font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
     color: #6b7280; border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f9fafb; }
.pos { color: #059669; font-weight: 600; }
.neg { color: #dc2626; font-weight: 600; }
.neutral { color: #6b7280; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px;
         font-size: 11px; font-weight: 600; }
.badge-stk { background: #dbeafe; color: #1d4ed8; }
.badge-opt { background: #fce7f3; color: #be185d; }
.badge-etf { background: #d1fae5; color: #065f46; }
.badge-call { background: #dbeafe; color: #1d4ed8; }
.badge-put  { background: #fee2e2; color: #991b1b; }
.alerts { list-style: none; }
.alerts li { padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;
             background: #fef3c7; border-left: 4px solid #f59e0b;
             font-size: 13px; color: #92400e; }
.alerts li.ok { background: #d1fae5; border-color: #059669; color: #065f46; }
.insights li { padding: 6px 0; border-bottom: 1px solid #f3f4f6; color: #374151; }
.insights li:last-child { border-bottom: none; }
.perf-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
             gap: 12px; margin-bottom: 16px; }
.perf-card { border: 1px solid #e5e7eb; border-radius: 6px; padding: 14px; }
.perf-card-label { font-size: 11px; text-transform: uppercase; color: #6b7280;
                   letter-spacing: .04em; margin-bottom: 4px; }
.perf-card-val { font-size: 17px; font-weight: 700; }
.bar-bg { background: #f3f4f6; border-radius: 9999px; height: 6px; margin-top: 4px; }
.bar-fill { height: 6px; border-radius: 9999px; }
.bar-pos { background: #059669; }
.bar-neg { background: #dc2626; }
"""


def render_html_report(
    portfolio: Portfolio,
    generated_at: datetime | None = None,
) -> str:
    report_time = generated_at or datetime.now(UTC)
    date_str = report_time.strftime("%Y-%m-%d %H:%M UTC")

    summary = portfolio.summary
    positions = portfolio.positions
    option_positions = [p for p in positions if p.asset_type == "OPT"]

    margin_util = margin_utilization(summary)
    invested_capital = summary.net_liquidation - summary.total_cash
    total_unrealized = sum(p.unrealized_pnl for p in positions)
    total_cost = sum(p.cost_basis for p in positions)
    portfolio_return = total_unrealized / total_cost if total_cost else 0.0

    coverage = cash_coverage(summary, positions)
    alerts = _build_alerts(portfolio, margin_util, coverage)
    insights = _build_insights(portfolio, margin_util, coverage)

    # --- performance by asset type ---
    perf_by_type: dict[str, tuple[float, float]] = {}
    for p in positions:
        pnl, cost = perf_by_type.get(p.asset_type, (0.0, 0.0))
        perf_by_type[p.asset_type] = (pnl + p.unrealized_pnl, cost + p.cost_basis)

    html_parts: list[str] = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>IBKR Positions — {report_time.strftime('%Y-%m-%d')}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<div class='container'>",
        "<h1>IBKR Positions Report</h1>",
        f"<div class='subtitle'>Account {portfolio.account_id} &nbsp;·&nbsp; {date_str}</div>",
    ]

    # --- summary cards ---
    nlv_cls = "pos" if summary.net_liquidation >= 0 else "neg"
    pnl_cls = "pos" if total_unrealized >= 0 else "neg"
    html_parts += [
        "<div class='cards'>",
        _card("Net Liquidation", _m(summary.net_liquidation), nlv_cls),
        _card("Total Cash", _m(summary.total_cash)),
        _card("Invested Capital", _m(invested_capital)),
        _card("Unrealized P&L", _m(total_unrealized, sign=True), pnl_cls),
        _card(
            "Margin Utilization",
            f"{margin_util:.1%}",
            "neg" if margin_util > 0.5 else ("neutral" if margin_util > 0.3 else ""),
        ),
        _card("Excess Liquidity", _m(summary.excess_liquidity)),
        "</div>",
    ]

    # --- performance section ---
    html_parts += ["<div class='section'>", "<h2>Performance</h2>"]

    # perf by type cards
    html_parts.append("<div class='perf-grid'>")
    for asset_type, (pnl, cost) in sorted(perf_by_type.items()):
        ret = pnl / cost if cost else 0.0
        pnl_cls = "pos" if pnl >= 0 else "neg"
        html_parts.append(
            f"<div class='perf-card'>"
            f"<div class='perf-card-label'>{asset_type}</div>"
            f"<div class='perf-card-val {pnl_cls}'>{_m(pnl, sign=True)}</div>"
            f"<div class='neutral' style='font-size:12px'>{ret:+.2%} return</div>"
            f"</div>"
        )
    # portfolio total
    html_parts.append(
        f"<div class='perf-card' style='border-color:#6366f1'>"
        f"<div class='perf-card-label'>Portfolio Total</div>"
        f"<div class='perf-card-val {'pos' if total_unrealized >= 0 else 'neg'}'>"
        f"{_m(total_unrealized, sign=True)}</div>"
        f"<div class='neutral' style='font-size:12px'>{portfolio_return:+.2%} return</div>"
        f"</div>"
    )
    html_parts.append("</div>")  # perf-grid

    # position performance table
    html_parts += [
        "<table>",
        "<thead><tr>",
        "<th>Symbol</th><th>Type</th><th>Qty</th>",
        "<th>Cost Basis</th><th>Market Value</th>",
        "<th>Unrealized P&L</th><th>Return %</th><th>Weight</th>",
        "</tr></thead>",
        "<tbody>",
    ]
    sorted_positions = sorted(
        positions, key=lambda p: abs(p.market_value), reverse=True
    )
    max_abs_pnl = max((abs(p.unrealized_pnl) for p in positions), default=1.0)
    for p in sorted_positions:
        ret = p.unrealized_pnl / p.cost_basis if p.cost_basis else 0.0
        weight = (
            abs(p.market_value) / summary.net_liquidation
            if summary.net_liquidation
            else 0.0
        )
        pnl_cls = "pos" if p.unrealized_pnl >= 0 else "neg"
        ret_cls = "pos" if ret >= 0 else "neg"
        badge_cls = f"badge-{p.asset_type.lower()}"
        bar_pct = min(abs(p.unrealized_pnl) / max_abs_pnl * 100, 100)
        bar_cls = "bar-pos" if p.unrealized_pnl >= 0 else "bar-neg"
        html_parts.append(
            f"<tr>"
            f"<td><strong>{p.symbol}</strong></td>"
            f"<td><span class='badge {badge_cls}'>{p.asset_type}</span></td>"
            f"<td>{p.quantity:+.0f}</td>"
            f"<td>{_m(p.cost_basis)}</td>"
            f"<td>{_m(p.market_value)}</td>"
            f"<td class='{pnl_cls}'>{_m(p.unrealized_pnl, sign=True)}"
            f"<div class='bar-bg'><div class='bar-fill {bar_cls}' style='width:{bar_pct:.0f}%'></div></div>"
            f"</td>"
            f"<td class='{ret_cls}'>{ret:+.2%}</td>"
            f"<td>{weight:.1%}</td>"
            f"</tr>"
        )
    html_parts += ["</tbody></table>", "</div>"]  # end performance section

    # --- options detail ---
    if option_positions:
        html_parts += [
            "<div class='section'>",
            "<h2>Open Options</h2>",
            "<table>",
            "<thead><tr>",
            "<th>Symbol</th><th>Underlying</th><th>Type</th>",
            "<th>Strike</th><th>Expiration</th><th>Qty</th>",
            "<th>Premium Recv'd</th><th>Current Value</th><th>P&L</th>",
            "</tr></thead><tbody>",
        ]
        for p in option_positions:
            opt_cls = f"badge-{(p.option_type or 'opt').lower()}"
            pnl_cls = "pos" if p.unrealized_pnl >= 0 else "neg"
            html_parts.append(
                f"<tr>"
                f"<td><strong>{p.symbol}</strong></td>"
                f"<td>{p.underlying or '—'}</td>"
                f"<td><span class='badge {opt_cls}'>{p.option_type or '—'}</span></td>"
                f"<td>{_m(p.strike or 0.0)}</td>"
                f"<td>{p.expiration or '—'}</td>"
                f"<td>{p.quantity:+.0f}</td>"
                f"<td>{_m(p.cost_basis)}</td>"
                f"<td>{_m(p.market_value)}</td>"
                f"<td class='{pnl_cls}'>{_m(p.unrealized_pnl, sign=True)}</td>"
                f"</tr>"
            )
        html_parts += ["</tbody></table>", "</div>"]

    # --- allocation ---
    html_parts += [
        "<div class='section'>",
        "<h2>Portfolio Allocation</h2>",
        "<table>",
        "<thead><tr><th>Asset Type</th><th>Market Value</th><th>% of NLV</th></tr></thead>",
        "<tbody>",
    ]
    allocation = _compute_allocation(positions, summary.net_liquidation)
    for asset_type, (value, pct) in allocation.items():
        html_parts.append(
            f"<tr><td>{asset_type}</td><td>{_m(value)}</td><td>{pct:.1%}</td></tr>"
        )
    cash_pct = (
        summary.total_cash / summary.net_liquidation if summary.net_liquidation else 0.0
    )
    html_parts.append(
        f"<tr><td>Cash</td><td>{_m(summary.total_cash)}</td><td>{cash_pct:.1%}</td></tr>"
    )
    html_parts += ["</tbody></table>", "</div>"]

    # --- cash by currency ---
    non_base_cash = [cb for cb in portfolio.cash if cb.currency != "BASE"]
    if non_base_cash:
        html_parts += [
            "<div class='section'>",
            "<h2>Cash by Currency</h2>",
            "<table>",
            "<thead><tr><th>Currency</th><th>Balance</th><th>Settled Cash</th></tr></thead>",
            "<tbody>",
        ]
        for cb in non_base_cash:
            html_parts.append(
                f"<tr><td>{cb.currency}</td><td>{_m(cb.balance)}</td><td>{_m(cb.settled_cash)}</td></tr>"
            )
        html_parts += ["</tbody></table>", "</div>"]

    # --- risk & alerts ---
    html_parts += ["<div class='section'>", "<h2>Risk Analysis</h2>"]
    if alerts:
        html_parts.append("<ul class='alerts'>")
        for a in alerts:
            html_parts.append(f"<li>{a}</li>")
        html_parts.append("</ul>")
    else:
        html_parts.append("<ul class='alerts'><li class='ok'>No alerts.</li></ul>")

    html_parts += [
        "<br>",
        "<table>",
        "<thead><tr><th>Margin Metric</th><th>Value</th></tr></thead>",
        "<tbody>",
        f"<tr><td>Margin Utilization</td><td class='{'neg' if margin_util > 0.5 else ''}'>{margin_util:.1%}</td></tr>",
        f"<tr><td>Initial Margin Required</td><td>{_m(summary.initial_margin)}</td></tr>",
        f"<tr><td>Maintenance Margin</td><td>{_m(summary.maintenance_margin)}</td></tr>",
        f"<tr><td>Excess Liquidity</td><td>{_m(summary.excess_liquidity)}</td></tr>",
        f"<tr><td>Buying Power</td><td>{_m(summary.buying_power)}</td></tr>",
        "</tbody></table>",
    ]

    if coverage["worst_case_assignment_cost"] > 0:
        covered = bool(coverage["covered"])
        cover_str = (
            "✓ Covered" if covered else f"✗ Shortfall {_m(coverage['shortfall'])}"
        )
        html_parts += [
            "<br><h2 style='margin-top:16px'>Cash Coverage (Short Puts)</h2>",
            "<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>",
            f"<tr><td>Worst-case Assignment Cost</td><td>{_m(coverage['worst_case_assignment_cost'])}</td></tr>",
            f"<tr><td>Available Cash</td><td>{_m(coverage['available_cash'])}</td></tr>",
            f"<tr><td>Status</td><td class='{'pos' if covered else 'neg'}'>{cover_str}</td></tr>",
            "</tbody></table>",
        ]
    html_parts.append("</div>")  # risk section

    # --- insights ---
    if insights:
        html_parts += [
            "<div class='section'>",
            "<h2>Actionable Insights</h2>",
            "<ul class='insights' style='padding-left:16px'>",
        ]
        for ins in insights:
            html_parts.append(f"<li>{ins}</li>")
        html_parts += ["</ul>", "</div>"]

    html_parts += [
        "<div style='text-align:center;color:#9ca3af;font-size:11px;margin-top:12px'>",
        f"Generated {date_str} · Account {portfolio.account_id}",
        "</div>",
        "</div>",  # container
        "</body></html>",
    ]
    return "\n".join(html_parts)


def write_html_report(
    portfolio: Portfolio,
    output_dir: str | Path = "reports/output",
    generated_at: datetime | None = None,
) -> Path:
    report_time = generated_at or datetime.now(UTC)
    date_str = report_time.strftime("%Y-%m-%d")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    html_path = output / f"ibkr_positions_{date_str}.html"
    html_path.write_text(
        render_html_report(portfolio, generated_at=report_time), encoding="utf-8"
    )
    return html_path


def _card(label: str, value: str, cls: str = "") -> str:
    return (
        f"<div class='card'>"
        f"<div class='card-label'>{label}</div>"
        f"<div class='card-value {cls}'>{value}</div>"
        f"</div>"
    )


def _m(value: float, sign: bool = False) -> str:
    prefix = "+" if sign and value >= 0 else ""
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"{prefix}${value:,.2f}"


def _compute_allocation(
    positions: list[Position], net_liquidation: float
) -> dict[str, tuple[float, float]]:
    buckets: dict[str, float] = {}
    for p in positions:
        buckets[p.asset_type] = buckets.get(p.asset_type, 0.0) + p.market_value
    return {
        at: (v, v / net_liquidation if net_liquidation else 0.0)
        for at, v in sorted(buckets.items())
    }


def _build_alerts(
    portfolio: Portfolio, margin_util: float, coverage: dict[str, float]
) -> list[str]:
    alerts: list[str] = []
    positions = portfolio.positions
    for symbol in concentration_risk(positions, threshold=0.25):
        alerts.append(
            f"Concentration risk: <strong>{symbol}</strong> exceeds 25% of portfolio"
        )
    for p in options_expiring_soon(positions, days=7):
        alerts.append(
            f"Option expiring soon: <strong>{p.symbol}</strong> expires {p.expiration} (qty {p.quantity:+.0f})"
        )
    for p in short_puts_near_assignment(positions):
        alerts.append(
            f"Short put near assignment: <strong>{p.symbol}</strong> strike {p.strike} vs underlying {p.underlying_price:.2f}"
        )
    for p in covered_calls_itm(positions):
        alerts.append(
            f"Covered call ITM: <strong>{p.symbol}</strong> strike {p.strike} vs underlying {p.underlying_price:.2f}"
        )
    if margin_util > 0.5:
        alerts.append(f"High margin utilization: {margin_util:.1%}")
    return alerts


def _build_insights(
    portfolio: Portfolio, margin_util: float, coverage: dict[str, float]
) -> list[str]:
    insights: list[str] = []
    option_positions = [p for p in portfolio.positions if p.asset_type == "OPT"]
    short_opts = [p for p in option_positions if p.quantity < 0]
    if short_opts:
        total_premium = sum(p.cost_basis for p in short_opts)
        insights.append(
            f"{len(short_opts)} short option position(s) generating premium — total received: {_m(total_premium)}"
        )
    if margin_util < 0.2:
        insights.append("Low margin utilization — significant capacity available")
    elif margin_util > 0.4:
        insights.append("Elevated margin utilization — consider reducing exposure")
    if coverage["worst_case_assignment_cost"] > 0:
        if coverage["covered"]:
            insights.append("Cash fully covers worst-case assignment of all short puts")
        else:
            insights.append(
                f"Cash shortfall of {_m(coverage['shortfall'])} if all short puts assigned"
            )
    return insights

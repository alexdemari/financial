from __future__ import annotations

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

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f1117; color: #e2e8f0; font-size: 14px; line-height: 1.5;
}
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; color: #f1f5f9; }
.subtitle { color: #64748b; font-size: 13px; margin-bottom: 24px; }
h2 { font-size: 15px; font-weight: 600; color: #cbd5e1; margin-bottom: 12px;
     padding-bottom: 6px; border-bottom: 1px solid #2d3139; }
.section { background: #151820; border: 1px solid #1e2230; border-radius: 8px;
           padding: 20px; margin-bottom: 20px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
         gap: 12px; margin-bottom: 20px; }
.card { background: #151820; border: 1px solid #1e2230; border-radius: 8px; padding: 16px; }
.card-label { font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
              color: #64748b; margin-bottom: 4px; }
.card-value { font-size: 20px; font-weight: 700; color: #f1f5f9; }
.card-value.pos { color: #34d399; }
.card-value.neg { color: #f87171; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #1e2230; text-align: left; padding: 8px 10px; font-weight: 600;
     font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
     color: #64748b; border-bottom: 1px solid #2d3139; white-space: nowrap; }
td { padding: 8px 10px; border-bottom: 1px solid #1a1d24; color: #cbd5e1; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #1a1d24; }
.pos { color: #34d399; font-weight: 600; }
.neg { color: #f87171; font-weight: 600; }
.neutral { color: #64748b; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px;
         font-size: 11px; font-weight: 600; }
.badge-stk { background: #1e3a5f; color: #60a5fa; }
.badge-opt { background: #3b1f3b; color: #e879f9; }
.badge-etf { background: #14362e; color: #34d399; }
.badge-call { background: #1e3a5f; color: #60a5fa; }
.badge-put  { background: #3b1414; color: #f87171; }
.alerts { list-style: none; }
.alerts li { padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;
             background: #2d2008; border-left: 4px solid #f59e0b;
             font-size: 13px; color: #fcd34d; }
.alerts li.ok { background: #0d2b1e; border-color: #34d399; color: #6ee7b7; }
.insights li { padding: 6px 0; border-bottom: 1px solid #1e2230; color: #94a3b8; }
.insights li:last-child { border-bottom: none; }
.perf-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
             gap: 12px; margin-bottom: 16px; }
.perf-card { border: 1px solid #2d3139; border-radius: 6px; padding: 14px;
             background: #0f1117; }
.perf-card-label { font-size: 11px; text-transform: uppercase; color: #64748b;
                   letter-spacing: .04em; margin-bottom: 4px; }
.perf-card-val { font-size: 17px; font-weight: 700; }
.bar-bg { background: #1e2230; border-radius: 9999px; height: 6px; margin-top: 4px; }
.bar-fill { height: 6px; border-radius: 9999px; }
.bar-pos { background: #34d399; }
.bar-neg { background: #f87171; }
p.neutral { color: #64748b; font-size: 13px; margin-top: 8px; }
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
        f"<div class='perf-card' style='border-color:#6366f1;background:#0f1117'>"
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

    # --- enhanced risk ---
    net_delta = portfolio_net_delta(portfolio)
    shortfall_actions = cash_shortfall_resolution(portfolio)
    concentration_details = _build_concentration_details(portfolio)
    delta_cls = (
        "pos" if net_delta > 0.10 else ("neg" if net_delta < -0.10 else "neutral")
    )
    html_parts += [
        "<div class='section'>",
        "<h2>Enhanced Risk</h2>",
        "<table>",
        "<thead><tr><th>Metric</th><th>Value</th><th>Context</th></tr></thead>",
        "<tbody>",
        f"<tr><td>Approximate Net Option Delta</td><td class='{delta_cls}'>{net_delta:+.2f}</td><td>{_delta_label(net_delta)}</td></tr>",
        "<tr><td>Delta Assumption</td><td>Approximate</td><td>Fixed 30% IV and 5% risk-free rate</td></tr>",
        "</tbody></table>",
        "<br><h2 style='margin-top:16px'>Cash Shortfall Resolution</h2>",
    ]
    if shortfall_actions:
        html_parts += [
            "<table>",
            "<thead><tr><th>Action</th><th>Symbol</th><th>Shortfall Reduction</th><th>Assignment Cost</th><th>Unrealized P&L</th></tr></thead>",
            "<tbody>",
        ]
        for action in shortfall_actions:
            pnl = float(action["unrealized_pnl"])
            html_parts.append(
                f"<tr>"
                f"<td>{action['action']}</td>"
                f"<td><strong>{action['symbol']}</strong></td>"
                f"<td>{_m(float(action['shortfall_reduction']))}</td>"
                f"<td>{_m(float(action['assignment_cost']))}</td>"
                f"<td class='{'pos' if pnl >= 0.0 else 'neg'}'>{_m(pnl, sign=True)}</td>"
                f"</tr>"
            )
        html_parts += ["</tbody></table>"]
    elif coverage["worst_case_assignment_cost"] > 0:
        html_parts.append(
            "<p class='neutral'>No shortfall action needed; cash covers short-put assignment risk.</p>"
        )
    else:
        html_parts.append(
            "<p class='neutral'>No short-put assignment cash shortfall.</p>"
        )

    html_parts.append("<br><h2 style='margin-top:16px'>Concentration Details</h2>")
    if concentration_details:
        html_parts += [
            "<table>",
            "<thead><tr><th>Symbol</th><th>% of NLV</th><th>Suggested Action</th></tr></thead>",
            "<tbody>",
        ]
        for detail in concentration_details:
            html_parts.append(
                f"<tr>"
                f"<td><strong>{detail['symbol']}</strong></td>"
                f"<td class='neg'>{float(detail['weight']):.1%}</td>"
                f"<td>{detail['suggested_action']}</td>"
                f"</tr>"
            )
        html_parts += ["</tbody></table>"]
    else:
        html_parts.append(
            "<p class='neutral'>No position exceeds the 25% concentration threshold.</p>"
        )
    html_parts.append("</div>")

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
        "<div style='text-align:center;color:#4b5563;font-size:11px;margin-top:24px;padding-top:16px;border-top:1px solid #1e2230'>",
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

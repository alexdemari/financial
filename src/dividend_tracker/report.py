from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dividend_tracker.decision import AssetDecision


def render_dividend_report(
    decisions: list[AssetDecision],
    budget: float | None = None,
    generated_at: datetime | None = None,
    processing_errors: list[str] | None = None,
    income_projections: list[dict] | None = None,
    usd_cash: float | None = None,
) -> str:
    report_time = generated_at or datetime.now(UTC)
    errors = processing_errors or []
    lines = [
        f"# Relatorio de Dividendos - {report_time:%d/%m/%Y %H:%M}",
        "",
        "## Resumo",
    ]
    counts = Counter(decision.action for decision in decisions)
    for action in ("BUY", "OVERPRICED"):
        tickers = [d.asset.ticker for d in decisions if d.action == action]
        suffix = f" ({', '.join(tickers)})" if tickers else ""
        lines.append(f"- {action}: {counts[action]} ativos{suffix}")
    if budget is not None:
        lines.append(f"- Budget disponivel: {format_money(budget, 'BRL')}")

    lines.extend(["", "## Ativos BR", ""])
    lines.extend(_render_asset_table(decisions, market="BR", currency="BRL"))
    lines.extend(["", "## Ativos US", ""])
    lines.extend(_render_asset_table(decisions, market="US", currency="USD"))

    if income_projections is not None:
        lines.extend(["", "## USD Income Projection (based on IBKR positions)", ""])
        lines.extend(_render_income_projection_section(income_projections, usd_cash))

    if errors:
        lines.extend(["", "## Erros de processamento", ""])
        lines.extend(f"- {error}" for error in errors)

    if budget is not None:
        lines.extend(["", f"## Guia de Aporte - {format_money(budget, 'BRL')}", ""])
        lines.extend(_render_budget_table(decisions, budget))

    monitored_decisions = [d for d in decisions if d.asset.target_weight == 0.0]
    if monitored_decisions:
        lines.extend(["", "## Ativos monitorados (sem alocacao de budget)", ""])
        lines.extend(_render_monitored_table(monitored_decisions))

    lines.extend(
        [
            "",
            "* Dividendo medio anual calculado sobre os ultimos 6 anos (metodologia AGF)",
            f"† min_dy customizado por ativo (override do global de {format_percent(_global_min_dy(decisions))})",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def write_dividend_report(
    decisions: list[AssetDecision],
    output_path: str | Path,
    budget: float | None = None,
    processing_errors: list[str] | None = None,
    income_projections: list[dict] | None = None,
    usd_cash: float | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_dividend_report(
            decisions,
            budget=budget,
            processing_errors=processing_errors,
            income_projections=income_projections,
            usd_cash=usd_cash,
        ),
        encoding="utf-8",
    )
    return output


def _render_asset_table(
    decisions: list[AssetDecision],
    market: str,
    currency: str,
) -> list[str]:
    rows = [
        "| Ticker | Setor | Preco Atual | Div. Base | Metodo | Preco Teto | DY Atual | min_dy | Margem | Decisao |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    market_decisions = [d for d in decisions if d.asset.market == market]
    if not market_decisions:
        rows.append("| - | - | - | - | - | - | - | - | - | - |")
        return rows

    for decision in market_decisions:
        ceiling = decision.price_ceiling
        dividend_base_marker = "*" if ceiling.ceiling_method == "average_6y" else ""
        min_dy_marker = " †" if decision.asset.min_dy is not None else ""
        rows.append(
            "| "
            f"{decision.asset.ticker} | "
            f"{decision.asset.sector} | "
            f"{format_money(ceiling.current_price, currency)} | "
            f"{format_money(ceiling.dividend_base, currency)}{dividend_base_marker} | "
            f"{_format_method(ceiling.ceiling_method)} | "
            f"{format_money(ceiling.price_ceiling, currency)} | "
            f"{format_percent(ceiling.current_dy)} | "
            f"{format_percent(ceiling.min_dy)}{min_dy_marker} | "
            f"{format_percent(ceiling.margin_pct, signed=True)} | "
            f"{_format_action(decision.action)} |"
        )
    return rows


def _render_budget_table(
    decisions: list[AssetDecision],
    budget: float,
) -> list[str]:
    eligible = [d for d in decisions if d.action == "BUY" and d.asset.target_weight > 0]
    if not eligible:
        return ["Nenhum ativo elegivel para aporte."]

    total_weight = sum(d.asset.target_weight for d in eligible)
    allocated_total = 0.0
    rows = [
        "| Ticker | Peso Alvo | Valor | Qtd | Preco Entrada |",
        "|---|---:|---:|---:|---:|",
    ]
    for decision in eligible:
        current_price = decision.price_ceiling.current_price
        allocated_value = (
            budget * (decision.asset.target_weight / total_weight)
            if total_weight > 0
            else 0.0
        )
        allocated_total += allocated_value
        quantity = int(allocated_value // current_price) if current_price > 0 else 0
        currency = "BRL" if decision.asset.market == "BR" else "USD"
        rows.append(
            "| "
            f"{decision.asset.ticker} | "
            f"{format_percent(decision.asset.target_weight)} | "
            f"{format_money(allocated_value, currency)} | "
            f"{quantity} | "
            f"<= {format_money(current_price, currency)} |"
        )
    remaining_budget = max(0.0, budget - allocated_total)
    rows.append(f"Budget restante nao alocado: {format_money(remaining_budget, 'BRL')}")
    return rows


def _render_monitored_table(decisions: list[AssetDecision]) -> list[str]:
    rows = [
        "| Ticker | Preco | Teto | DY atual | min_dy | Decisao | Nota |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for decision in decisions:
        ceiling = decision.price_ceiling
        currency = "BRL" if decision.asset.market == "BR" else "USD"
        rows.append(
            "| "
            f"{decision.asset.ticker} | "
            f"{format_money(ceiling.current_price, currency)} | "
            f"{format_money(ceiling.price_ceiling, currency)} | "
            f"{format_percent(ceiling.current_dy)} | "
            f"{format_percent(ceiling.min_dy)} | "
            f"{_format_action(decision.action)} | "
            f"{decision.asset.notes or '-'} |"
        )
    return rows


def _render_income_projection_section(
    projections: list[dict],
    usd_cash: float | None,
) -> list[str]:
    if not projections:
        lines = ["No IBKR STK positions matched dividend portfolio assets."]
    else:
        lines = [
            "| Symbol | Shares | Div/Share/Year | Projected Annual Income | DY on Cost |",
            "|---|---:|---:|---:|---:|",
        ]
        for row in projections:
            lines.append(
                "| "
                f"{row['symbol']} | "
                f"{row['shares']:.0f} | "
                f"US${row['annual_div_per_share']:.2f} | "
                f"US${row['projected_annual_income_usd']:,.0f}/year | "
                f"{row['dy_on_cost_pct']:.1f}% |"
            )
        total = sum(r["projected_annual_income_usd"] for r in projections)
        lines.append("")
        lines.append(
            f"**Total projected USD income:** US${total:,.0f}/year"
            f" (~US${total / 12:,.0f}/month)"
        )

    if usd_cash is not None:
        lines.append(f"**USD cash available (IBKR):** US${usd_cash:,.2f}")

    lines.append(
        "\n*Note: projections use trailing 12-month dividends per share."
        " Not a guarantee of future income.*"
    )
    return lines


def format_money(value: float, currency: str) -> str:
    prefix = "R$" if currency == "BRL" else "US$"
    return f"{prefix}{value:,.2f}"


def format_percent(value: float, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value * 100:.1f}%"


def _format_action(action: str) -> str:
    if action == "BUY":
        return "**BUY**"
    return f"**{action}**"


def _format_method(ceiling_method: str) -> str:
    if ceiling_method == "average_6y":
        return "Media 6a"
    return "TTM"


def _global_min_dy(decisions: list[AssetDecision]) -> float:
    non_custom = [d.price_ceiling.min_dy for d in decisions if d.asset.min_dy is None]
    if non_custom:
        return non_custom[0]
    return 0.06

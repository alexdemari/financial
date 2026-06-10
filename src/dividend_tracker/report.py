from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dividend_tracker.decision import AssetDecision


def render_dividend_report(
    decisions: list[AssetDecision],
    budget: float | None = None,
    generated_at: datetime | None = None,
    processing_errors: list[str] | None = None,
) -> str:
    report_time = generated_at or datetime.now(UTC)
    errors = processing_errors or []
    lines = [
        f"# Relatorio de Dividendos - {report_time:%d/%m/%Y %H:%M}",
        "",
        "## Resumo",
    ]
    counts = Counter(decision.decision for decision in decisions)
    for decision_name in ("BUY", "WATCH", "WAIT", "OVERPRICED"):
        tickers = [
            decision.asset.ticker
            for decision in decisions
            if decision.decision == decision_name
        ]
        suffix = f" ({', '.join(tickers)})" if tickers else ""
        lines.append(f"- {decision_name}: {counts[decision_name]} ativos{suffix}")
    if budget is not None:
        lines.append(f"- Budget disponivel: {format_money(budget, 'BRL')}")

    lines.extend(["", "## Ativos BR", ""])
    lines.extend(_render_asset_table(decisions, market="BR", currency="BRL"))
    lines.extend(["", "## Ativos US", ""])
    lines.extend(_render_asset_table(decisions, market="US", currency="USD"))
    lines.extend(["", "## Detalhes por ativo", ""])
    lines.extend(_render_details(decisions))

    if errors:
        lines.extend(["", "## Erros de processamento", ""])
        lines.extend(f"- {error}" for error in errors)

    if budget is not None:
        lines.extend(["", f"## Guia de Aporte - {format_money(budget, 'BRL')}", ""])
        lines.extend(_render_budget_table(decisions, budget))

    monitored_decisions = [
        decision for decision in decisions if decision.asset.target_weight == 0.0
    ]
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
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_dividend_report(
            decisions,
            budget=budget,
            processing_errors=processing_errors,
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
        "| Ticker | Setor | Preco Atual | Div. Base | Metodo | Preco Teto | DY Atual | min_dy | Margem | Sinal Tecnico | Decisao |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---|---|",
    ]
    market_decisions = [
        decision for decision in decisions if decision.asset.market == market
    ]
    if not market_decisions:
        rows.append("| - | - | - | - | - | - | - | - | - | - | - |")
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
            f"{decision.technical_signal.signal} | "
            f"**{decision.decision}** |"
        )
    return rows


def _render_details(decisions: list[AssetDecision]) -> list[str]:
    actionable = [
        decision for decision in decisions if decision.decision in {"BUY", "WATCH"}
    ]
    if not actionable:
        return ["Nenhum ativo em BUY ou WATCH."]

    lines: list[str] = []
    for decision in actionable:
        ceiling = decision.price_ceiling
        technical_signal = decision.technical_signal
        lines.extend(
            [
                f"### {decision.asset.ticker} - {decision.asset.name}",
                "",
                f"- Dividendo base ({ceiling.dividend_base_label}): {ceiling.dividend_base:.2f}",
                f"- Dividendos TTM: {ceiling.trailing_annual_dividends:.2f}",
                f"- Historico recente: {_format_distributions(ceiling)}",
                (
                    "- Sinal tecnico: "
                    f"{technical_signal.model} / {technical_signal.event_type} / "
                    f"{_format_days(technical_signal.days_since_event)}"
                ),
                f"- Justificativa: {decision.description}",
                "",
            ]
        )
    return lines


def _render_budget_table(decisions: list[AssetDecision], budget: float) -> list[str]:
    eligible = [
        decision
        for decision in decisions
        if decision.decision in {"BUY", "WATCH"} and decision.asset.target_weight > 0
    ]
    if not eligible:
        return ["Nenhum ativo elegivel para aporte."]

    total_weight = sum(decision.asset.target_weight for decision in eligible)
    rows = [
        "| Ticker | Peso Alvo | Valor | Qtd Acoes | Preco Entrada |",
        "|---|---:|---:|---:|---:|",
    ]
    for decision in eligible:
        current_price = decision.price_ceiling.current_price
        allocated_value = (
            budget * (decision.asset.target_weight / total_weight)
            if total_weight > 0
            else 0.0
        )
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
    return rows


def _render_monitored_table(decisions: list[AssetDecision]) -> list[str]:
    rows = [
        "| Ticker | Motivo | Decisao hoje | Proxima acao sugerida |",
        "|---|---|---|---|",
    ]
    for decision in decisions:
        rows.append(
            "| "
            f"{decision.asset.ticker} | "
            f"{decision.asset.notes or 'Monitorado sem alocacao de budget'} | "
            f"**{decision.decision}** | "
            f"{_suggest_next_action(decision)} |"
        )
    return rows


def format_money(value: float, currency: str) -> str:
    prefix = "R$" if currency == "BRL" else "US$"
    return f"{prefix}{value:,.2f}"


def format_percent(value: float, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value * 100:.1f}%"


def _format_days(days_since_event: int | None) -> str:
    if days_since_event is None:
        return "sem evento recente"
    if days_since_event == 0:
        return "hoje"
    return f"{days_since_event} dias desde o evento"


def _format_distributions(ceiling) -> str:
    if not ceiling.recent_distributions:
        return "sem distribuicoes no cache"
    return ", ".join(
        f"{distribution.date:%Y-%m-%d}: {distribution.amount:.2f}"
        for distribution in ceiling.recent_distributions
    )


def _format_method(ceiling_method: str) -> str:
    if ceiling_method == "average_6y":
        return "Media 6a"
    return "TTM"


def _suggest_next_action(decision: AssetDecision) -> str:
    if decision.decision == "BUY":
        return "Avaliar entrada conforme plano"
    if decision.decision == "WATCH":
        return "Monitorar gatilho tecnico"
    if decision.decision == "OVERPRICED":
        return "Aguardar preco teto"
    return "Aguardar novo sinal"


def _global_min_dy(decisions: list[AssetDecision]) -> float:
    non_custom = [
        decision.price_ceiling.min_dy
        for decision in decisions
        if decision.asset.min_dy is None
    ]
    if non_custom:
        return non_custom[0]
    return 0.06

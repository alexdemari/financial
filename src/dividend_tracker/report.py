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
        "| Ticker | Setor | Preco Atual | Preco Teto | DY Atual | Margem | Sinal Tecnico | Decisao |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    market_decisions = [
        decision for decision in decisions if decision.asset.market == market
    ]
    if not market_decisions:
        rows.append("| - | - | - | - | - | - | - | - |")
        return rows

    for decision in market_decisions:
        ceiling = decision.price_ceiling
        rows.append(
            "| "
            f"{decision.asset.ticker} | "
            f"{decision.asset.sector} | "
            f"{format_money(ceiling.current_price, currency)} | "
            f"{format_money(ceiling.price_ceiling, currency)} | "
            f"{format_percent(ceiling.current_dy)} | "
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
        decision for decision in decisions if decision.decision in {"BUY", "WATCH"}
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

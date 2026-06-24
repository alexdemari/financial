from __future__ import annotations

from datetime import date
from pathlib import Path

from irpf_report.calculator import AssetTypeSummary, EnrichedTrade, MonthSummary, Totals


def _fmt_usd(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}${v:,.2f}"


def _fmt_brl(v: float | None, incomplete: bool = False) -> str:
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    suffix = "*" if incomplete else ""
    return f"{sign}R${v:,.2f}{suffix}"


def render_markdown(
    year: int,
    trades: list[EnrichedTrade],
    monthly: list[MonthSummary],
    asset_type_summaries: list[AssetTypeSummary],
    totals: Totals,
) -> str:
    lines: list[str] = []
    lines.append(f"# IRPF {year + 1} — Rendimentos no Exterior (ano-base {year})\n")
    lines.append(f"Gerado em {date.today().isoformat()}\n")

    if totals.brl_incomplete:
        lines.append(
            "> **Aviso:** uma ou mais operações não têm taxa PTAX disponível (API BCB indisponível). "
            "Os totais em BRL marcados com `*` estão **incompletos** e não devem ser usados para declaração.\n"
        )

    # Per-trade table — full spec columns
    lines.append("## Operações Encerradas\n")
    lines.append(
        "| Data | Símbolo | Tipo | Qtd | Proceeds USD | Custo USD | Resultado USD "
        "| PTAX | Proceeds BRL | Custo BRL | Resultado BRL |"
    )
    lines.append(
        "|------|---------|------|-----|-------------|----------|--------------|"
        "------|-------------|---------|--------------|"
    )
    for t in trades:
        ptax_str = f"{t.ptax_rate:.4f}" if t.ptax_rate is not None else "N/A"
        missing = t.ptax_rate is None
        lines.append(
            f"| {t.date} | {t.symbol} | {t.asset_type} | {t.quantity:g} "
            f"| {_fmt_usd(t.proceeds_usd)} | {_fmt_usd(t.cost_usd)} | {_fmt_usd(t.pnl_usd)} "
            f"| {ptax_str} "
            f"| {_fmt_brl(t.proceeds_brl, missing)} "
            f"| {_fmt_brl(t.cost_brl, missing)} "
            f"| {_fmt_brl(t.pnl_brl, missing)} |"
        )

    # Asset-type aggregation
    lines.append("")
    lines.append("## Resultado por Tipo de Ativo\n")
    lines.append(
        "| Tipo | Operações | Ganhos USD | Perdas USD | Líquido USD "
        "| Ganhos BRL | Perdas BRL | Líquido BRL |"
    )
    lines.append(
        "|------|-----------|-----------|-----------|------------|-----------|-----------|------------|"
    )
    for s in asset_type_summaries:
        inc = s.brl_incomplete
        lines.append(
            f"| {s.asset_type} | {s.trade_count} "
            f"| {_fmt_usd(s.gross_gain_usd)} | {_fmt_usd(s.gross_loss_usd)} | {_fmt_usd(s.net_usd)} "
            f"| {_fmt_brl(s.gross_gain_brl, inc)} "
            f"| {_fmt_brl(s.gross_loss_brl, inc)} "
            f"| {_fmt_brl(s.net_brl, inc)} |"
        )

    # Annual summary
    lines.append("")
    lines.append("## Resumo Anual\n")
    lines.append("| | USD | BRL |")
    lines.append("|---|---|---|")
    inc = totals.brl_incomplete
    lines.append(
        f"| Ganhos totais | {_fmt_usd(totals.gain_usd)} | {_fmt_brl(totals.gain_brl, inc)} |"
    )
    lines.append(
        f"| Perdas totais | {_fmt_usd(totals.loss_usd)} | {_fmt_brl(totals.loss_brl, inc)} |"
    )
    lines.append(
        f"| **Resultado líquido** | **{_fmt_usd(totals.net_usd)}** | **{_fmt_brl(totals.net_brl, inc)}** |"
    )

    # Monthly breakdown
    lines.append("")
    lines.append("## Breakdown Mensal\n")
    lines.append("| Mês | Ganhos BRL | Perdas BRL | Líquido BRL |")
    lines.append("|-----|-----------|-----------|-------------|")
    for m in monthly:
        lines.append(
            f"| {m.month} | {_fmt_brl(m.gross_gain_brl)} "
            f"| {_fmt_brl(m.gross_loss_brl)} | {_fmt_brl(m.net_brl)} |"
        )

    lines.append("")
    lines.append("---")
    lines.append(
        "*Nota: este relatório tem finalidade informativa. A apuração do imposto devido "
        "deve ser feita no Programa IRPF da Receita Federal, considerando todos os "
        "rendimentos do ano-calendário. Consulte um contador.*"
    )
    if totals.brl_incomplete:
        lines.append(
            "\n*`*` = valor BRL incompleto — PTAX não disponível para esta operação.*"
        )

    return "\n".join(lines) + "\n"


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

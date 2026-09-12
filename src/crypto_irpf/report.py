"""Markdown rendering for the crypto section of the IRPF report."""

from datetime import date

from crypto_irpf.apuracao import ApuracaoMensal
from crypto_irpf.earn import EarnSummary


def format_section(
    monthly: list[ApuracaoMensal],
    earn_summary: EarnSummary,
    year: int,
    holdings: dict[str, dict[str, float]],
) -> str:
    """Render a standalone section suitable for the consolidated IRPF report."""
    lines = ["## Criptoativos Binance\n", "### Resumo do Ano\n"]
    lines.extend(
        [
            "| Mês | Total Vendas R$ | Custo R$ | Ganho/Perda R$ | Status | DARF |",
            "|-----|----------------:|---------:|----------------:|--------|-----:|",
        ]
    )
    for item in monthly:
        status = "ISENTO" if item.isento else "TRIBUTÁVEL"
        darf = (
            "—"
            if not item.darf_valor
            else f"R$ {item.darf_valor:,.2f} ({item.darf_vencimento})"
        )
        lines.append(
            f"| {item.ano_mes} | R$ {item.total_vendas_brl:,.2f} | R$ {item.total_custo_brl:,.2f} | R$ {item.ganho_liquido_brl:,.2f} | {status} | {darf} |"
        )
    if not monthly:
        lines.append("| — | R$ 0.00 | R$ 0.00 | R$ 0.00 | — | — |")
    lines.extend(
        [
            "\n### Detalhamento por Alienação\n",
            "| Data | Ativo | Qtde | Preço PTAX R$ | Custo Médio R$ | Ganho/Perda R$ |",
            "|------|-------|-----:|---------------:|----------------:|----------------:|",
        ]
    )
    for item in monthly:
        for sale in item.trades:
            price = sale.proceeds_brl / sale.quantity if sale.quantity else 0.0
            lines.append(
                f"| {sale.date} | {sale.asset} | {sale.quantity:g} | R$ {price:,.2f} | R$ {sale.average_cost_brl:,.2f} | R$ {sale.gain_loss_brl:,.2f} |"
            )
    lines.extend(
        [
            "\n### Rendimentos de Aplicação Financeira (Simple Earn / Staking)\n",
            "| Tipo | Valor R$ (PTAX) |",
            "|------|----------------:|",
        ]
    )
    for earn_type, amount in earn_summary.by_type_brl.items():
        lines.append(f"| {earn_type} | R$ {amount:,.2f} |")
    lines.append(f"| **Total** | **R$ {earn_summary.total_brl:,.2f}** |")
    lines.extend(
        [
            "\n### Bens e Direitos em 31/12\n",
            "| Criptoativo | Quantidade | Custo de Aquisição R$ |",
            "|-------------|-----------:|----------------------:|",
        ]
    )
    for asset, holding in sorted(holdings.items()):
        if holding["quantity"] > 0.00000001:
            lines.append(
                f"| {asset} | {holding['quantity']:g} | R$ {holding['cost_brl']:,.2f} |"
            )
    if not any(holding["quantity"] > 0.00000001 for holding in holdings.values()):
        lines.append("| (nenhum) | — | — |")
    lines.extend(
        [
            "",
            "*Rendimentos EARN devem ser declarados como rendimentos recebidos de fontes no exterior. Consulte um contador para validação.*",
            f"\n*Relatório gerado em {date.today().isoformat()}.*",
        ]
    )
    return "\n".join(lines) + "\n"

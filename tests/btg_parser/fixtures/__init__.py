from __future__ import annotations

from pathlib import Path

import openpyxl


def build_xlsx(path: Path, sheets: dict[str, list[list]]) -> Path:
    """Write a minimal XLSX with the given sheet name -> row data mapping."""
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in rows:
            worksheet.append(row)
    workbook.save(path)
    return path


def renda_variavel_rows() -> list[list]:
    return [
        ["Renda Variável"],
        [None],
        ["Posição"],
        ["Posição > Ações"],
        [
            "Código",
            "Ação",
            "Qtde.",
            "Preço Fechamento R$",
            "Preço Médio R$",
            "Saldo Bruto R$",
        ],
        ["TAEE11", "TAESA UNT N2", 251, 39.78, 39.78, 9984.78],
        ["Total em Ações R$", "", "", "", "", 9984.78],
        [None],
        ["Movimentação"],
        ["Movimentação > Ações"],
        [
            "Data",
            "Transação",
            "Código",
            "Qtde.",
            "Preço R$",
            "Valor Bruto R$",
            "Corretagem e Emolumentos R$",
            "Valor Líquido R$",
        ],
        ["2026-06-12", "COMPRA", "TAEE11", 251, 39.77, 9982.27, 3.0, 9985.27],
        ["2026-06-13", "VENDA", "TAEE11", 100, 40.0, 4000.0, 1.0, 3999.0],
        ["Total de Compras", "", "", "", "", 9982.27, 3.0, 9985.27],
        ["Total de Vendas", "", "", "", "", 4000.0, 1.0, 3999.0],
        [None],
        ["Posição"],
        ["Posição > Opções"],
        [
            "Código",
            "Ativo Ref.",
            "Qtde.",
            "Preço Exercício R$",
            "Data Exercício R$",
            "Tipo",
            "Posição",
            "Prêmio Mercado R$",
            "Valor de Mercado R$",
            "Preço de Prêmio R$",
        ],
        [
            "BBASH212",
            "BB ON",
            1000,
            20.9,
            "2026-08-21",
            "Call",
            "Comprada",
            0.55,
            550.91,
            "-",
        ],
        ["Total em Opções R$", "", "", "", "", "", "", "", 550.91, ""],
        [None],
        ["Movimentação"],
        ["Movimentação > Opções"],
        [
            "Data",
            "Transação",
            "Tipo",
            "Código",
            "Data Exercício",
            "Prêmio de Mercado R$",
            "Qtde. de Contratos",
            "Prêmio Pago/Recebido R$",
            "Valor Financeiro Bruto R$",
            "Corretagem e Emolumentos R$",
        ],
        [
            "2026-05-06",
            "VENDA",
            "Put",
            "EGIER324",
            "2026-06-19",
            0.45,
            -500,
            -224.71,
            -225,
            -0.21,
        ],
        ["Total de Compras", "", "", "", "", "", "", "", 0, ""],
    ]
